"""Health probe for ChainLens Research & Ingest engine."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import httpx

from app.config import config
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


def _sanitize_chainlens_error(error: str | None, api_key: str | None, base_url: str | None) -> str | None:
    """Redact any API key / token values from the error text or URL."""
    if not error:
        return error
    if api_key:
        error = error.replace(api_key, "***")
    if base_url:
        error = error.replace(base_url, "<chainlens_base_url>")
    return error


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

    async def _sample_search(self, base_url: str, token: str, timeout: float) -> tuple[HealthStatus, str | None, int]:
        """Run a lightweight search query to verify ChainLens search is functional."""
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.post(
                    f"{base_url.rstrip('/')}/api/v1/research",
                    headers=headers,
                    json={
                        "query": "health check",
                        "max_results": 1,
                    },
                )
            latency_ms = int((time.perf_counter() - start) * 1000)
            if resp.status_code == 200:
                return ("healthy", None, latency_ms)
            if resp.status_code in (401, 403):
                return ("degraded", f"ChainLens search rejected auth (HTTP {resp.status_code})", latency_ms)
            if resp.status_code == 429:
                return ("degraded", "ChainLens search rate limited", latency_ms)
            if resp.status_code >= 500:
                return ("unavailable", f"ChainLens search returned HTTP {resp.status_code}", latency_ms)
            return ("degraded", f"ChainLens search returned HTTP {resp.status_code}", latency_ms)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ("unavailable", f"ChainLens search failed: {type(exc).__name__}", latency_ms)

    async def _health_endpoint(self, base_url: str, token: str, timeout: float) -> tuple[HealthStatus, str | None, int]:
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.get(f"{base_url.rstrip('/')}/api/v1/health", headers=headers)
            latency_ms = int((time.perf_counter() - start) * 1000)
            if resp.status_code == 200:
                return ("healthy", None, latency_ms)
            if resp.status_code in (401, 403):
                return ("degraded", f"Authentication rejected with HTTP {resp.status_code}", latency_ms)
            if resp.status_code == 429:
                return ("degraded", "ChainLens health endpoint rate limited", latency_ms)
            if resp.status_code >= 500:
                return ("unavailable", f"Health check returned HTTP {resp.status_code}", latency_ms)
            return ("degraded", f"Health check returned HTTP {resp.status_code}", latency_ms)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ("unavailable", f"{type(exc).__name__}: {exc}", latency_ms)

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        latency_ms: int | None = None

        base_url = getattr(config, "CHAINLENS_API_URL", None) or "https://api.chainlens.ai"
        api_key = getattr(config, "CHAINLENS_SERVICE_TOKEN", None) or getattr(config, "CHAINLENS_API_KEY", None)

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
            # 1. Health endpoint
            health_status, health_error, health_latency = await self._health_endpoint(base_url, api_key, timeout=5.0)
            # 2. Sample search probe
            search_status, search_error, search_latency = await self._sample_search(base_url, api_key, timeout=10.0)

            # Aggregate status: worst of the two, but prefer the explicit meaning
            if health_status == "unavailable" or search_status == "unavailable":
                status = "unavailable"
                last_error = _sanitize_chainlens_error(health_error or search_error, api_key, base_url)
            elif health_status == "degraded" or search_status == "degraded":
                status = "degraded"
                last_error = _sanitize_chainlens_error(health_error or search_error, api_key, base_url)
            else:
                status = "healthy"

            latency_ms = max(health_latency, search_latency)
            if status == "healthy" and latency_ms > 5000:
                status = "degraded"
                last_error = "ChainLens latency above threshold"

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = _sanitize_chainlens_error(f"{type(exc).__name__}: {exc}", api_key, base_url)

        success_rate = 100.0 if status == "healthy" else (50.0 if status == "degraded" else 0.0)
        error_rate = 0.0 if status == "healthy" else (50.0 if status == "degraded" else 100.0)

        safe_metadata = {
            "endpoint": base_url,
            "configured": True,
        }

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
            metadata=safe_metadata,
            probed_at=datetime.now(UTC),
        )
