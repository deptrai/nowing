"""Health probe for ChainLens Research & Ingest engine."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import httpx

from app.config import config
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class ChainLensHealthProbe(HealthProbe):
    """Probes ChainLens Research service availability and latency."""

    def __init__(
        self,
        service_id: str = "chainlens/research",
        service_name: str = "ChainLens Research Engine",
    ) -> None:
        self._service_id = service_id
        self._service_name = service_name

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "research"

    @property
    def display_group(self) -> str:
        return "Research & Search"

    @property
    def interval_seconds(self) -> int:
        return 300  # 5 minutes

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        latency_ms: int | None = None

        base_url = getattr(config, "CHAINLENS_API_URL", None) or "https://api.chainlens.ai"
        api_key = getattr(config, "CHAINLENS_API_KEY", None)

        if not api_key:
            return HealthResult(
                service_id=self._service_id,
                service_name=self._service_name,
                category=self.category,
                display_group=self.display_group,
                status="not_configured",
                latency_ms=0,
                last_error=None,
                error_rate_15m=0.0,
                success_rate_15m=100.0,
                metadata={"endpoint": base_url, "configured": False},
                probed_at=datetime.now(UTC),
            )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = await client.get(f"{base_url.rstrip('/')}/api/v1/health", headers=headers)
                latency_ms = int((time.perf_counter() - start) * 1000)

                if resp.status_code == 200:
                    status = "healthy" if latency_ms < 3000 else "degraded"
                elif resp.status_code in {401, 403}:
                    status = "degraded"
                    last_error = f"Authentication rejected with HTTP {resp.status_code}"
                else:
                    status = "degraded"
                    last_error = f"Health check returned HTTP {resp.status_code}"
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"{type(exc).__name__}: {exc}"

        success_rate = 100.0 if status == "healthy" else (50.0 if status == "degraded" else 0.0)
        error_rate = 0.0 if status == "healthy" else (50.0 if status == "degraded" else 100.0)

        return HealthResult(
            service_id=self._service_id,
            service_name=self._service_name,
            category=self.category,
            display_group=self.display_group,
            status=status,
            latency_ms=latency_ms,
            last_error=last_error,
            error_rate_15m=error_rate,
            success_rate_15m=success_rate,
            metadata={"endpoint": base_url, "configured": True},
            probed_at=datetime.now(UTC),
        )
