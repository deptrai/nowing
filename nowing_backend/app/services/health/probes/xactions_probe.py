"""Health probe for XActions MCP service (Story 21.8a / AD-SOC-11)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.proprietary.platforms.xactions.mcp_client import XActionsMcpClient
from app.services.health.probe_base import HealthProbe, HealthResult

logger = logging.getLogger(__name__)


class XActionsHealthProbe(HealthProbe):
    """Check XActions MCP daemon health via `x_governor_status`."""

    service_id = "scraper/xactions"
    service_name = "XActions Social Graph"
    category = "scraper"
    display_group = "B2B Lead Intelligence"
    interval_seconds = 300  # 5 minutes

    async def probe(self) -> HealthResult:
        start = datetime.now(UTC)
        try:
            async with XActionsMcpClient() as client:
                result = await client.call_tool("x_governor_status", {})
                governor_data = result.get("data", {})

                metrics_result = await client.call_tool("x_admin_stream_metrics", {})
                metrics_data = metrics_result.get("metrics", {})

                # Determine status from governor health
                healthy_proxies = governor_data.get("healthyProxies", 0)
                backpressure = governor_data.get("backpressure", "none")

                if backpressure == "critical" or healthy_proxies == 0:
                    status = "unavailable"
                    error = "XActions backpressure critical or no healthy proxies"
                elif backpressure == "moderate" or healthy_proxies < 3:
                    status = "degraded"
                    error = f"Low healthy proxies: {healthy_proxies}"
                else:
                    status = "healthy"
                    error = None

                return HealthResult(
                    service_id=self.service_id,
                    service_name=self.service_name,
                    category=self.category,
                    display_group=self.display_group,
                    status=status,
                    latency_ms=int(
                        (datetime.now(UTC) - start).total_seconds() * 1000
                    ),
                    last_error=error,
                    suggested_action="Check XActions proxy pool and governor" if status != "healthy" else None,
                    metadata={
                        "healthy_proxies": healthy_proxies,
                        "backpressure": backpressure,
                        "stream_metrics": metrics_data,
                    },
                    probed_at=datetime.now(UTC),
                    interval_seconds=self.interval_seconds,
                    next_probe_at=datetime.now(UTC).replace(
                        microsecond=0
                    ) + timedelta(seconds=self.interval_seconds),
                )
        except Exception as exc:
            logger.exception("XActions health probe failed")
            return HealthResult(
                service_id=self.service_id,
                service_name=self.service_name,
                category=self.category,
                display_group=self.display_group,
                status="unavailable",
                latency_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
                last_error=f"MCP connection failed: {type(exc).__name__}",
                suggested_action="Verify XACTIONS_MCP_URL and XActions daemon is running",
                metadata={},
                probed_at=datetime.now(UTC),
                interval_seconds=self.interval_seconds,
                next_probe_at=datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=self.interval_seconds),
            )
