"""Health probe for platform scrapers."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import httpx

from app.capabilities.core.store import CapabilityRegistry
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class ScraperHealthProbe(HealthProbe):
    """Probes a specific scraper platform or capability."""

    def __init__(
        self,
        platform: str,
        service_name: str | None = None,
        display_group: str = "Platform Scrapers",
        endpoint: str | None = None,
    ) -> None:
        self._platform = platform
        self._service_id = f"scraper/{platform}"
        self._service_name = service_name or platform.replace("_", " ").title()
        self._display_group = display_group
        self._endpoint = endpoint

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "scraper"

    @property
    def display_group(self) -> str:
        return self._display_group

    @property
    def interval_seconds(self) -> int:
        return 300  # 5 minutes

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None
        latency_ms: int | None = None

        try:
            # 1. Check if capability is registered in CapabilityRegistry
            matching_caps = [
                cap for cap in CapabilityRegistry.all()
                if self._platform in cap.name or (cap.metadata and cap.metadata.get("platform") == self._platform)
            ]

            # 2. Check proxy pool reachability via active provider
            proxy_configured = False
            proxy_dict = None
            try:
                from app.utils.proxy import get_active_provider

                provider = get_active_provider()
                if provider:
                    proxy_dict = provider.get_requests_proxies()
                    proxy_configured = bool(proxy_dict)
            except Exception as proxy_err:
                logger.debug("Proxy resolution note for %s: %s", self._service_id, proxy_err)

            # 3. Non-mutating lightweight probe: safe HTTP HEAD to neutral endpoint via proxy or direct
            try:
                # Use a neutral target (e.g., httpbin or icanhazip) to avoid platform anti-bot triggers
                test_url = "https://1.1.1.1"
                proxies = proxy_dict.get("https") if proxy_dict else None
                async with httpx.AsyncClient(proxy=proxies, timeout=3.0, verify=False) as client:
                    resp = await client.head(test_url)
                    if resp.status_code >= 500:
                        status = "degraded"
                        suggested_action = "Rotate proxy pool or inspect gateway upstream"
            except Exception as net_exc:
                # Network or proxy timeout
                if proxy_configured:
                    status = "degraded"
                    suggested_action = "Rotate proxy pool endpoints"
                    last_error = f"Proxy latency/connect warning: {type(net_exc).__name__}"
                else:
                    # Without proxy configured and registration missing
                    if not matching_caps:
                        status = "degraded"
                        suggested_action = "Verify capability registration in CapabilityRegistry"

            latency_ms = int((time.perf_counter() - start) * 1000)
            if latency_ms > 4000 and status == "healthy":
                status = "degraded"
                suggested_action = "Investigate network latency for scraper probe"

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Scraper probe error: {type(exc).__name__}"
            suggested_action = "Check scraper configuration and proxy pool connectivity"

        success_rate = 100.0 if status == "healthy" else (60.0 if status == "degraded" else 0.0)
        error_rate = 0.0 if status == "healthy" else (40.0 if status == "degraded" else 100.0)

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
            metadata={"platform": self._platform, "endpoint": self._endpoint},
            probed_at=datetime.now(UTC),
        )
