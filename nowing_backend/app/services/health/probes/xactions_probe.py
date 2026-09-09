"""Health probe for XActions MCP service (Story 21.8a / AD-SOC-11)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.alerts.engine.execute import execute_alert_rule
from app.alerts.persistence.models.alert_rule import AlertRule
from app.db import async_session_maker
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
                governor_data = result.get("data", {}) or {}
                if isinstance(governor_data, list):
                    governor_data = governor_data[0] if governor_data else {}

                try:
                    metrics_result = await client.call_tool("x_admin_stream_metrics", {})
                    metrics_data = metrics_result.get("metrics") or metrics_result.get("data") or {}
                    if isinstance(metrics_data, list):
                        metrics_data = metrics_data[0] if metrics_data else {}
                        metrics_data = metrics_data.get("metrics") or metrics_data
                except Exception:
                    metrics_data = {}

                # AC 9: evaluate XActions stream alerts and trigger admin alerts
                # via the Nowing alert engine when a breach is reported.
                try:
                    alerts_result = await client.call_tool("x_admin_stream_alerts", {})
                    alerts = alerts_result.get("data") or alerts_result.get("alerts") or []
                    if isinstance(alerts, list):
                        first = alerts[0] if alerts else {}
                        alerts = first.get("alerts") if isinstance(first, dict) else first
                except Exception:
                    alerts = []

                # Determine status from governor health (XActions returns
                # `healthyProxyCount`; keep fallbacks for older payloads).
                healthy_proxies = governor_data.get("healthyProxyCount") or governor_data.get("healthyProxies") or 0
                backpressure = governor_data.get("backpressure") or "none"

                if backpressure == "critical" or healthy_proxies == 0:
                    status = "unavailable"
                    error = "XActions backpressure critical or no healthy proxies"
                elif backpressure == "moderate" or healthy_proxies < 3:
                    status = "degraded"
                    error = f"Low healthy proxies: {healthy_proxies}"
                else:
                    status = "healthy"
                    error = None

                # If XActions reports an active stream alert, mark degraded
                # and, if admin rules exist, fire matching alert rules.
                active_alerts = alerts.get("activeAlerts") if isinstance(alerts, dict) else alerts
                if active_alerts:
                    status = "degraded"
                    error = error or f"XActions stream alert: {active_alerts[0]!s}"
                    await self._fire_alert_rules_for_stream_breach(active_alerts)

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
                        "stream_alerts": alerts,
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
                next_probe_at=datetime.now(UTC).replace(
                    microsecond=0
                ) + timedelta(seconds=self.interval_seconds),
            )

    async def _fire_alert_rules_for_stream_breach(self, alerts: list) -> None:
        """Fire Nowing alert rules for XActions stream breach reports.

        AC 9 requires Telegram/Email notification when XActions admin stream
        alerts are reported. We look up admin/global alert rules that have
        capability "health" (or use a generic admin social trigger) and call
        execute_alert_rule for each match. Exact matching is intentionally
        broad because XActions alert shapes vary by deployment.
        """
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(AlertRule).where(
                        AlertRule.enabled.is_(True),
                        AlertRule.capability_id == "xactions_admin_stream",
                    )
                )
                rules = result.scalars().all()
                if not rules:
                    logger.info(
                        "XActions stream alerts present but no matching AlertRule; skip firing"
                    )
                    return

                fired_at = datetime.now(UTC)
                for rule in rules:
                    try:
                        await execute_alert_rule(
                            session=session,
                            alert_rule=rule,
                            fired_at=fired_at,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to fire XActions stream alert rule %s", rule.id
                        )
                await session.commit()
        except Exception:
            logger.exception("Failed to evaluate XActions stream alert rules")
