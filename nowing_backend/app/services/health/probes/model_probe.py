"""Health probe for LLM, vision, and embedding models."""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db import async_session_maker
from app.models.admin_health import AdminHealthHistory
from app.models.connectors import Connection
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus
from app.services.model_connection_service import verify_connection

logger = logging.getLogger(__name__)

_SECRET_PATTERN = re.compile(r"(key|token|secret|password|bearer\s+|auth\s+)[=:\s]*([^\s,;&]+)", re.IGNORECASE)


def _sanitize_string(text: str | None) -> str | None:
    if not text:
        return text
    return _SECRET_PATTERN.sub(r"\1=***", text)


class ModelHealthProbe(HealthProbe):
    """Probes a specific global or registered model connection."""

    def __init__(
        self,
        service_id: str,
        service_name: str,
        provider: str,
        model_id: str = "",
        display_group: str = "Chat Models",
        connection: Connection | None = None,
        base_url: str | None = None,
    ) -> None:
        self._service_id = service_id
        self._service_name = service_name
        self._provider = provider
        self._model_id = model_id
        self._display_group = display_group
        self._connection = connection
        self._base_url = base_url

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "model"

    @property
    def display_group(self) -> str:
        return self._display_group

    @property
    def interval_seconds(self) -> int:
        return 120  # 2 minutes

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "unavailable"
        last_error: str | None = None
        suggested_action: str | None = None
        latency_ms: int | None = None

        try:
            if self._provider.lower() == "vllm" or self._service_id == "local/vllm":
                from app.services.hybrid_llm_router import HybridLLMRouter

                router = HybridLLMRouter()
                is_healthy = await router._vllm_health()
                latency_ms = int((time.perf_counter() - start) * 1000)
                if is_healthy:
                    status = "healthy" if latency_ms < 3000 else "degraded"
                    if status == "degraded":
                        suggested_action = "Check GPU memory and queue concurrency on vLLM node"
                else:
                    status = "unavailable"
                    last_error = "vLLM server unreachable or returned unhealthy status"
                    suggested_action = "Restart local vLLM container or inspect GPU logs"

            elif self._connection is not None:
                verify_res = await verify_connection(self._connection)
                latency_ms = int((time.perf_counter() - start) * 1000)
                if verify_res.verified:
                    status = "healthy" if latency_ms < 3000 else "degraded"
                    if status == "degraded":
                        suggested_action = "Monitor model response latency"
                else:
                    if verify_res.code in {"AUTH_FAILED", "NOT_FOUND"} and not (
                        self._connection.api_key or self._connection.credentials
                    ):
                        status = "not_configured"
                        suggested_action = "Provide API credentials for this model provider"
                    elif verify_res.code == "RATE_LIMITED":
                        status = "degraded"
                        suggested_action = "Increase provider quota or check rate limits"
                    else:
                        status = "unavailable"
                        suggested_action = "Check API key validity and provider endpoint reachability"
                    last_error = _sanitize_string(verify_res.message)

            else:
                # Standalone verification without DB Connection model
                temp_conn = Connection(
                    provider=self._provider,
                    base_url=self._base_url,
                    extra={"model_ids": [self._model_id]} if self._model_id else {},
                )
                verify_res = await verify_connection(temp_conn)
                latency_ms = int((time.perf_counter() - start) * 1000)
                if verify_res.verified:
                    status = "healthy" if latency_ms < 3000 else "degraded"
                    if status == "degraded":
                        suggested_action = "Monitor model response latency"
                else:
                    if verify_res.code in {"AUTH_FAILED", "NOT_FOUND"}:
                        status = "not_configured"
                        suggested_action = f"Configure credentials for {self._provider.upper()}"
                    elif verify_res.code == "RATE_LIMITED":
                        status = "degraded"
                        suggested_action = "Increase provider quota or check rate limits"
                    else:
                        status = "unavailable"
                        suggested_action = "Verify model provider endpoint and status page"
                    last_error = _sanitize_string(verify_res.message)

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = _sanitize_string(f"Probe execution error: {type(exc).__name__}")
            suggested_action = "Verify model connection credentials and network routes"

        # Compute 15-minute success/error rate from actual history
        success_rate = 100.0 if status in {"healthy", "degraded", "not_configured"} else 0.0
        error_rate = 0.0 if status in {"healthy", "not_configured"} else (50.0 if status == "degraded" else 100.0)

        try:
            async with async_session_maker() as session:
                cutoff = datetime.now(UTC) - timedelta(minutes=15)
                tot_query = select(func.count()).select_from(AdminHealthHistory).where(
                    AdminHealthHistory.service_id == self._service_id,
                    AdminHealthHistory.probe_at >= cutoff,
                )
                err_query = select(func.count()).select_from(AdminHealthHistory).where(
                    AdminHealthHistory.service_id == self._service_id,
                    AdminHealthHistory.probe_at >= cutoff,
                    AdminHealthHistory.status.in_(["unavailable"]),
                )
                tot_res = await session.execute(tot_query)
                err_res = await session.execute(err_query)
                tot_count = tot_res.scalar() or 0
                err_count = err_res.scalar() or 0
                if tot_count > 0:
                    error_rate = round((err_count / tot_count) * 100.0, 1)
                    success_rate = round(100.0 - error_rate, 1)
        except Exception as hist_exc:
            logger.debug("History calculation note for %s: %s", self._service_id, hist_exc)

        safe_metadata = {
            "provider": self._provider,
            "model_id": self._model_id,
            "base_url": _sanitize_string(self._base_url),
        }

        return HealthResult(
            service_id=self._service_id,
            service_name=self._service_name,
            category=self.category,
            display_group=self.display_group,
            status=status,
            latency_ms=latency_ms,
            last_error=last_error,
            suggested_action=suggested_action,
            error_rate_15m=error_rate,
            success_rate_15m=success_rate,
            metadata=safe_metadata,
            probed_at=datetime.now(UTC),
        )
