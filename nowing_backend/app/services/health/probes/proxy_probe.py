"""Health probe for proxy and anti-bot network egress."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.services.admin_telemetry_service import AdminTelemetryService
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class ProxyHealthProbe(HealthProbe):
    """Probes the active proxy pool and egress connectivity."""

    def __init__(self, service_id: str = "proxy/dataimpulse", service_name: str = "DataImpulse Proxy Pool") -> None:
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
        return "proxy"

    @property
    def display_group(self) -> str:
        return "Proxy & Anti-Bot"

    @property
    def interval_seconds(self) -> int:
        return 300  # 5 minutes

    async def probe(self) -> HealthResult:
        telemetry_service = AdminTelemetryService(session=None)  # type: ignore[arg-type]
        raw = await telemetry_service.get_proxy_health()

        raw_status = raw.get("status", "dead")
        if raw_status == "healthy":
            status: HealthStatus = "healthy"
        elif raw_status == "degraded":
            status = "degraded"
        elif raw_status == "not_configured":
            status = "not_configured"
        else:
            status = "unavailable"

        latency_ms = raw.get("latency_ms")
        if latency_ms is None and raw.get("snapshots"):
            latency_ms = raw["snapshots"][0].get("latency_ms")

        last_error = raw.get("last_error")
        if not last_error and raw.get("snapshots"):
            last_error = raw["snapshots"][0].get("last_error")

        success_rate = raw.get("success_rate", 100.0 if status in {"healthy", "degraded"} else 0.0)
        error_rate = 100.0 - success_rate

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
            metadata={
                "provider": raw.get("provider", "unknown"),
                "total": raw.get("total", 0),
                "healthy": raw.get("healthy", 0),
                "degraded": raw.get("degraded", 0),
                "dead": raw.get("dead", 0),
            },
            probed_at=datetime.now(UTC),
        )
