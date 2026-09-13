from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.services.proxy_health_cache import (
    get_proxy_health_snapshot,
    update_proxy_health_snapshot,
)
from app.utils.proxy import get_active_provider

from ._helpers import _redact_error, _redact_url

logger = logging.getLogger(__name__)


class ProxyHealthMixin:
    async def get_proxy_health(self) -> dict[str, Any]:
        """Return a cached snapshot of the active proxy provider's health.

        Probes are best-effort, throttled to once per 10 seconds per process.
        """
        provider = get_active_provider()
        provider_name = getattr(provider, "name", "unknown")
        proxy_url = provider.get_proxy_url()

        if not proxy_url:
            return {
                "status": "not_configured",
                "provider": provider_name,
                "snapshots": [],
                "total": 0,
                "healthy": 0,
                "degraded": 0,
                "dead": 0,
            }

        # Throttle: use a per-process cache to avoid hammering the proxy
        cached = get_proxy_health_snapshot()
        if cached is not None:
            return cached

        proxies = provider.get_requests_proxies()
        # httpx 0.28.1 uses ``proxy=`` with a URL string, not ``proxies=``.
        proxy_for_client = (
            proxies.get("https") or proxies.get("http") if proxies else None
        )
        start = time.perf_counter()
        last_error: str | None = None
        latency_ms: int | None = None
        status = "dead"

        try:
            async with httpx.AsyncClient(
                proxy=proxy_for_client, timeout=5.0, follow_redirects=True
            ) as client:
                response = await client.head("https://www.google.com")
                elapsed_ms = (time.perf_counter() - start) * 1000
                latency_ms = int(elapsed_ms)
                if response.status_code < 400:
                    if latency_ms <= 500:
                        status = "healthy"
                    elif latency_ms <= 2000:
                        status = "degraded"
                    else:
                        status = "dead"
                else:
                    status = "dead"
                    last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # pragma: no cover - network failures; probe degrades to "dead" status
            status = "dead"
            last_error = _redact_error(f"{type(exc).__name__}: {exc}")
            latency_ms = int((time.perf_counter() - start) * 1000)

        snapshot = {
            "provider": provider_name,
            "url": _redact_url(proxy_url),
            "latency_ms": latency_ms,
            "success_rate": 100.0 if status in {"healthy", "degraded"} else 0.0,
            "status": status,
            "last_error": _redact_error(last_error),
            "last_probed_at": datetime.now(UTC),
        }

        result = {
            "status": status,
            "provider": provider_name,
            "snapshots": [snapshot],
            "total": 1,
            "healthy": 1 if status == "healthy" else 0,
            "degraded": 1 if status == "degraded" else 0,
            "dead": 1 if status == "dead" else 0,
        }
        update_proxy_health_snapshot(result)
        return result
