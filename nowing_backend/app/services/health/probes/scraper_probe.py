"""Health probe for platform scrapers."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import httpx

from app.capabilities.core.store import CapabilityRegistry
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


# Platform -> canonical docs/health landing or CDN endpoint
_CANONICAL_PLATFORM_ENDPOINTS: dict[str, str] = {
    "amazon": "https://www.amazon.com",
    "batdongsan": "https://batdongsan.com.vn",
    "cafef": "https://cafef.vn",
    "chotot": "https://www.chotot.com",
    "crawler": "https://httpbin.org/get",
    "google_maps": "https://maps.googleapis.com",
    "google_search": "https://www.google.com",
    "indeed": "https://www.indeed.com",
    "instagram": "https://www.instagram.com",
    "itviec": "https://itviec.com",
    "linkedin": "https://www.linkedin.com",
    "masothue": "https://masothue.com",
    "muaban_bds": "https://muaban.net",
    "muasamcong": "https://muasamcong.gov.vn",
    "reddit": "https://www.reddit.com",
    "shopee": "https://shopee.vn",
    "spatial_planning": "https://httpbin.org/get",
    "telegram": "https://t.me",
    "tiktok": "https://www.tiktok.com",
    "topcv": "https://www.topcv.vn",
    "vietnamworks": "https://www.vietnamworks.com",
    "vietstock": "https://vietstock.vn",
    "walmart": "https://www.walmart.com",
    "xactions": "https://x.com",
    "youtube": "https://www.youtube.com",
}


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
        self._endpoint = endpoint or _CANONICAL_PLATFORM_ENDPOINTS.get(platform, "https://httpbin.org/get")

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

    def _is_cap_registered(self) -> bool:
        """Check whether a capability is registered in the CapabilityRegistry for this platform."""
        for cap in CapabilityRegistry.all():
            if self._platform in cap.name:
                return True
            if cap.metadata:
                if cap.metadata.get("platform") == self._platform:
                    return True
                if cap.metadata.get("category") in ("scraper", "search"):
                    return True
        return False

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None
        latency_ms: int | None = None

        cap_registered = self._is_cap_registered()

        # 1. Check proxy pool reachability via active provider
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

        # 2. Non-mutating lightweight probe: safe HTTP HEAD to platform endpoint via proxy or direct
        try:
            proxy_url = proxy_dict.get("http") if proxy_dict else None
            async with httpx.AsyncClient(proxy=proxy_url, timeout=3.0, follow_redirects=True) as client:
                resp = await client.head(self._endpoint)
                if resp.status_code >= 500:
                    status = "degraded"
                    suggested_action = "Rotate proxy pool or inspect gateway upstream"
                elif resp.status_code in (401, 403, 407):
                    # Auth walls are expected for some platforms; only report degraded if proxy is absent
                    if not proxy_configured:
                        status = "degraded"
                        suggested_action = "Ensure proxy or credentials are configured for this platform"
                    last_error = f"HTTP {resp.status_code} from {self._endpoint}"
                elif resp.status_code >= 400:
                    status = "degraded"
                    suggested_action = "Verify target endpoint and proxy configuration"
                    last_error = f"HTTP {resp.status_code} from {self._endpoint}"
        except Exception as net_exc:
            if proxy_configured:
                status = "degraded"
                suggested_action = "Rotate proxy pool endpoints"
                last_error = f"Proxy latency/connect warning: {type(net_exc).__name__}: {net_exc}"
            else:
                # No proxy and capability not registered -> not really a failure, just not configured
                if not cap_registered:
                    status = "not_configured"
                    suggested_action = "Verify capability registration in CapabilityRegistry"
                    last_error = f"No capability registered and network probe failed: {type(net_exc).__name__}"
                else:
                    status = "unavailable"
                    suggested_action = "Verify target endpoint and proxy configuration"
                    last_error = f"Network probe failed: {type(net_exc).__name__}: {net_exc}"

        latency_ms = int((time.perf_counter() - start) * 1000)
        if latency_ms > 4000 and status in {"healthy", "degraded"}:
            status = "degraded"
            suggested_action = suggested_action or "Investigate network latency for scraper probe"

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
            suggested_action=suggested_action,
            error_rate_15m=error_rate,
            success_rate_15m=success_rate,
            metadata={"platform": self._platform, "endpoint": self._endpoint, "capability_registered": cap_registered},
            probed_at=datetime.now(UTC),
        )
