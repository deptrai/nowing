"""Unified facade for third-party health monitoring, probes, alerts, and history."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_health import (
    AdminHealthAlert,
    AdminHealthHistory,
    AdminHealthStatus,
)
from app.services.health.alert_engine import AdminHealthAlertEngine
from app.services.health.probe_base import HealthResult
from app.services.health.registry import HealthProbeRegistry
from app.services.health.result_store import HealthResultStore
from app.services.health.scheduler import HealthProbeScheduler

logger = logging.getLogger(__name__)


class ThirdPartyHealthService:
    """Facade for managing third-party probes, snapshots, alerts, and history."""

    @staticmethod
    def list_categories() -> list[dict[str, Any]]:
        """Return metadata for every registered health probe category."""
        probes = HealthProbeRegistry.get_probes()
        by_category: dict[str, list] = {}
        for probe in probes:
            by_category.setdefault(probe.category, []).append(probe)

        category_meta = {
            "infra": ("Infrastructure", 30),
            "model": ("LLM / AI Models", 120),
            "scraper": ("Platform Scrapers", 300),
            "connector": ("SaaS Connectors", 900),
            "messaging": ("Messaging & Notifications", 300),
            "payment": ("Payment Providers", 300),
            "storage": ("Storage Backends", 300),
            "research": ("ChainLens Research", 300),
            "proxy": ("Proxy Pool", 300),
        }

        items = []
        for key in sorted(by_category.keys()):
            probe_count = len(by_category[key])
            first = by_category[key][0]
            label, default_interval = category_meta.get(key, (key.replace("_", " ").title(), first.interval_seconds))
            items.append(
                {
                    "key": key,
                    "label": label,
                    "default_interval_seconds": default_interval,
                    "probe_count": probe_count,
                }
            )
        return items

    @staticmethod
    async def get_overview(session: AsyncSession) -> dict[str, Any]:
        """Compute aggregated health overview across all categories."""
        statuses = await HealthResultStore.get_latest_status(session)
        alerts = await AdminHealthAlertEngine.get_active_alerts(session)

        status_counts = {
            "healthy": 0,
            "degraded": 0,
            "unavailable": 0,
            "not_configured": 0,
            "disabled": 0,
        }

        category_summary: dict[str, dict[str, int]] = {}

        for item in statuses:
            st = item.status if item.status in status_counts else "unavailable"
            status_counts[st] += 1

            cat = item.category
            if cat not in category_summary:
                category_summary[cat] = {
                    "total": 0,
                    "healthy": 0,
                    "degraded": 0,
                    "unavailable": 0,
                    "not_configured": 0,
                    "disabled": 0,
                }
            category_summary[cat]["total"] += 1
            if st in category_summary[cat]:
                category_summary[cat][st] += 1

        total = sum(status_counts.values())
        if total == 0:
            overall_status = "not_configured"
        else:
            unavailable_ratio = status_counts["unavailable"] / total
            if unavailable_ratio == 1.0:
                overall_status = "unavailable"
            elif unavailable_ratio >= 0.5 or status_counts["unavailable"] > 0:
                overall_status = "degraded"
            elif status_counts["degraded"] > 0:
                overall_status = "degraded"
            else:
                overall_status = "healthy"

        return {
            "overall_status": overall_status,
            "total_monitored": len(statuses),
            "status_counts": status_counts,
            "active_alerts_count": len(alerts),
            "categories": category_summary,
            "registered_categories": HealthProbeRegistry.get_categories(),
        }

    @staticmethod
    async def get_statuses(
        session: AsyncSession,
        category: str | None = None,
        service_id: str | None = None,
    ) -> list[AdminHealthStatus]:
        """Fetch current status snapshots."""
        return await HealthResultStore.get_latest_status(session, category=category, service_id=service_id)

    @staticmethod
    async def get_history(
        session: AsyncSession,
        service_id: str,
        hours: int = 24,
        limit: int = 10000,
        offset: int = 0,
    ) -> list[AdminHealthHistory]:
        """Fetch historical probe logs for a service."""
        return await HealthResultStore.get_history(session, service_id=service_id, hours=hours, limit=limit, offset=offset)

    @staticmethod
    async def run_category_probes(
        session: AsyncSession,
        category: str,
    ) -> list[HealthResult]:
        """Trigger on-demand category probe run."""
        return await HealthProbeScheduler.run_category(category, session=session)

    @staticmethod
    async def run_single_probe(
        session: AsyncSession,
        service_id: str,
    ) -> HealthResult | None:
        """Trigger on-demand single probe execution."""
        return await HealthProbeScheduler.run_single(service_id, session=session)

    @staticmethod
    async def get_active_alerts(session: AsyncSession) -> list[AdminHealthAlert]:
        """List active incidents/alerts."""
        return await AdminHealthAlertEngine.get_active_alerts(session)

    @staticmethod
    async def acknowledge_alert(
        session: AsyncSession,
        alert_id: int,
        user_id: UUID | None = None,
        duration_minutes: int = 60,
    ) -> AdminHealthAlert | None:
        """Acknowledge an alert to suppress banners/notifications."""
        return await AdminHealthAlertEngine.acknowledge_alert(
            session=session,
            alert_id=alert_id,
            acknowledged_by=user_id,
            duration_minutes=duration_minutes,
        )

    @staticmethod
    async def resolve_alert(
        session: AsyncSession,
        alert_id: int,
    ) -> AdminHealthAlert | None:
        """Manually resolve an active alert."""
        return await AdminHealthAlertEngine.resolve_alert(session=session, alert_id=alert_id)

    @staticmethod
    async def list_rules(session: AsyncSession) -> list[AdminHealthAlertRule]:
        """List admin health alert rules."""
        return await AdminHealthAlertEngine.get_rules(session)

    @staticmethod
    async def get_rule(session: AsyncSession, rule_id: int) -> AdminHealthAlertRule | None:
        """Get a single admin health alert rule."""
        return await AdminHealthAlertEngine.get_rule(session, rule_id)

    @staticmethod
    async def create_rule(
        session: AsyncSession,
        rule: AdminHealthAlertRule,
    ) -> AdminHealthAlertRule:
        """Create a new admin health alert rule."""
        return await AdminHealthAlertEngine.create_rule(session, rule)

    @staticmethod
    async def update_rule(
        session: AsyncSession,
        rule: AdminHealthAlertRule,
    ) -> AdminHealthAlertRule:
        """Update an admin health alert rule."""
        return await AdminHealthAlertEngine.update_rule(session, rule)

    @staticmethod
    async def delete_rule(session: AsyncSession, rule_id: int) -> bool:
        """Delete an admin health alert rule."""
        return await AdminHealthAlertEngine.delete_rule(session, rule_id)
