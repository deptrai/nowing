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

        overall_status = "healthy"
        if status_counts["unavailable"] > 0:
            overall_status = "degraded"  # or unavailable if major
        elif status_counts["degraded"] > 0:
            overall_status = "degraded"

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
    ) -> list[AdminHealthHistory]:
        """Fetch historical probe logs for a service."""
        return await HealthResultStore.get_history(session, service_id=service_id, hours=hours)

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
