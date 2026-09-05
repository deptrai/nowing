"""Health probe for LLM, vision, and embedding models."""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime

from app.config import config
from app.models.connectors import Connection
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus
from app.services.model_connection_service import verify_connection

logger = logging.getLogger(__name__)

_SECRET_PATTERN = re.compile(
    r"(key|token|secret|password|bearer\s+|auth\s+|api[-_]?key)[=:\s]*([^\s,;&\"\']+)",
    re.IGNORECASE,
)

# Standard URL userinfo credential pattern (e.g. https://user:pass@host)
_URL_CRED_PATTERN = re.compile(r"^(\w+://)[^@]+@", re.IGNORECASE)


def _sanitize_string(text: str | None) -> str | None:
    if not text:
        return text
    text = _URL_CRED_PATTERN.sub(r"\1***:***@", text)
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

    @staticmethod
    def _connection_from_global_config(provider: str, model_name: str) -> Connection:
        """Build a Connection from in-memory global LLM config for the provider/model."""
        for cfg in getattr(config, "GLOBAL_LLM_CONFIGS", []) or []:
            provider_match = cfg.get("litellm_provider") == provider or cfg.get("provider") == provider
            model_match = not model_name or (cfg.get("model_name") == model_name or cfg.get("name") == model_name)
            if provider_match and model_match:
                from app.services.model_resolver import (
                    native_connection_from_config,
                )

                conn_dict = native_connection_from_config(cfg)
                return Connection(
                    provider=conn_dict["provider"],
                    base_url=conn_dict["base_url"],
                    api_key=conn_dict.get("api_key"),
                    extra=conn_dict.get("extra", {}),
                )
        return Connection(
            provider=provider,
            base_url=None,
            api_key=None,
            extra={},
        )

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    def _has_credentials(self) -> bool:
        """Check whether the probe has enough credentials for a real API call."""
        if self._connection is not None:
            return bool(self._connection.api_key or (self._connection.extra or {}).get("api_key"))
        for cfg in getattr(config, "GLOBAL_LLM_CONFIGS", []) or []:
            if (
                cfg.get("litellm_provider") == self._provider
                or cfg.get("provider") == self._provider
            ) and (cfg.get("api_key") or cfg.get("credentials")):
                return True
        return False

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

            elif not self._has_credentials():
                status = "not_configured"
                suggested_action = f"Configure API credentials for {self._provider.upper()}"

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
                # Standalone verification using global config or DB fallback
                temp_conn = self._connection_from_global_config(self._provider, self._model_id)
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

        # Success/error rate is computed by HealthResultStore from actual history.
        # We leave the defaults as the current probe's outcome so that callers
        # without persisted history still see a sensible instantaneous value.
        success_rate = 100.0 if status in {"healthy", "not_configured"} else (50.0 if status == "degraded" else 0.0)
        error_rate = 100.0 - success_rate

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
