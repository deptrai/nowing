"""Health Alert Engine for evaluating threshold rules, deduplicating, and dispatching alerts."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_health import (
    AdminHealthAlert,
    AdminHealthAlertRule,
    AdminHealthHistory,
    AdminHealthStatus,
)
from app.services.health.probe_base import HealthResult

logger = logging.getLogger(__name__)


class AdminHealthAlertEngine:
    """Evaluates probe results against health alert rules, dedupes, and emits incidents."""

    @classmethod
    async def evaluate_result(
        cls,
        session: AsyncSession,
        result: HealthResult,
    ) -> list[AdminHealthAlert]:
        """Evaluate a single probe result against matching active rules."""
        now = datetime.now(UTC)

        # 1. Auto-resolve logic: if result is healthy, resolve open alerts for this service
        if result.status == "healthy":
            open_alerts_stmt = select(AdminHealthAlert).where(
                AdminHealthAlert.service_id == result.service_id,
                AdminHealthAlert.status.in_(["open", "acknowledged"]),
            )
            open_res = await session.execute(open_alerts_stmt)
            open_alerts = open_res.scalars().all()
            for oa in open_alerts:
                oa.status = "resolved"
                oa.resolved_at = now
                oa.updated_at = now
            if open_alerts:
                await session.commit()
            return []

        # Query active rules matching category or global
        stmt = select(AdminHealthAlertRule).where(AdminHealthAlertRule.enabled.is_(True))
        res = await session.execute(stmt)
        rules = res.scalars().all()

        triggered_alerts: list[AdminHealthAlert] = []

        for rule in rules:
            if rule.category and rule.category != result.category:
                continue

            # Check service_id_pattern matching
            if rule.service_id_pattern:
                try:
                    pattern = re.compile(rule.service_id_pattern)
                    if not pattern.search(result.service_id):
                        continue
                except Exception as exc:
                    logger.warning("Invalid regex pattern '%s' in rule %s: %s", rule.service_id_pattern, rule.id, exc)
                    continue

            matches = await cls._check_rule_condition(session, rule, result)
            if not matches:
                continue

            # Check deduplication & existing open/acknowledged alert
            existing_alert_stmt = select(AdminHealthAlert).where(
                AdminHealthAlert.service_id == result.service_id,
                AdminHealthAlert.rule_id == rule.id,
                AdminHealthAlert.status.in_(["open", "acknowledged"]),
            )
            existing_res = await session.execute(existing_alert_stmt)
            existing_alert = existing_res.scalar_one_or_none()

            if existing_alert is not None:
                # Update triggered_at to now instead of creating duplicate
                existing_alert.triggered_at = now
                existing_alert.updated_at = now
                continue

            # Create new incident alert
            msg = (
                f"[{rule.severity.upper()}] Service '{result.service_name}' ({result.service_id}) "
                f"status '{result.status}'. {result.last_error or 'Alert threshold triggered.'}"
            )
            alert = AdminHealthAlert(
                rule_id=rule.id,
                service_id=result.service_id,
                status="open",
                severity=rule.severity,
                message=msg,
                triggered_at=now,
            )
            session.add(alert)
            triggered_alerts.append(alert)

            # Dispatch notification (in-app, email, telegram)
            await cls._dispatch_notification(session, rule, alert, result)

        if triggered_alerts:
            await session.commit()

        return triggered_alerts

    @classmethod
    async def _check_rule_condition(
        cls,
        session: AsyncSession,
        rule: AdminHealthAlertRule,
        result: HealthResult,
    ) -> bool:
        """Inspect rule condition JSON against the current and recent probe state."""
        cond = rule.condition_json or {}

        # 1. Direct status check
        target_status = cond.get("status")
        consecutive_probes = cond.get("consecutive_probes", 1)

        if target_status:
            if result.status != target_status:
                return False
            if consecutive_probes > 1:
                hist_stmt = (
                    select(AdminHealthHistory.status)
                    .where(AdminHealthHistory.service_id == result.service_id)
                    .order_by(AdminHealthHistory.probe_at.desc())
                    .limit(consecutive_probes)
                )
                hist_res = await session.execute(hist_stmt)
                past_statuses = hist_res.scalars().all()
                if len(past_statuses) < consecutive_probes or any(s != target_status for s in past_statuses):
                    return False
            return True

        # 2. Status not check (e.g. status != 'healthy')
        status_not = cond.get("status_not")
        if status_not:
            if result.status == status_not:
                return False
            if consecutive_probes > 1:
                hist_stmt = (
                    select(AdminHealthHistory.status)
                    .where(AdminHealthHistory.service_id == result.service_id)
                    .order_by(AdminHealthHistory.probe_at.desc())
                    .limit(consecutive_probes)
                )
                hist_res = await session.execute(hist_stmt)
                past_statuses = hist_res.scalars().all()
                if len(past_statuses) < consecutive_probes or any(s == status_not for s in past_statuses):
                    return False
            return True

        # 3. Metric threshold check (e.g. success_rate_15m < 50.0)
        metric = cond.get("metric")
        op = cond.get("op")
        threshold = cond.get("threshold")
        if metric == "success_rate_15m" and op == "<" and threshold is not None:
            return result.success_rate_15m < float(threshold)

        return False

    @classmethod
    async def _dispatch_notification(
        cls,
        session: AsyncSession,
        rule: AdminHealthAlertRule,
        alert: AdminHealthAlert,
        result: HealthResult,
    ) -> None:
        """Best-effort notification dispatch to configured channels (in-app, email, telegram)."""
        try:
            channels = rule.channels or ["in_app"]
            logger.info(
                "Dispatching admin health alert %s for service %s to channels %s",
                alert.id,
                result.service_id,
                channels,
            )

            # Query superusers for notification delivery
            from app.db import User

            su_stmt = select(User).where(User.is_superuser.is_(True))
            su_res = await session.execute(su_stmt)
            superusers = list(su_res.scalars().all())

            if "in_app" in channels:
                from app.notifications.service import NotificationService

                for su in superusers:
                    try:
                        await NotificationService.create_notification(
                            session=session,
                            user_id=su.id,
                            notification_type="admin_health_alert",
                            title=f"Third-Party Health Alert: {result.service_name}",
                            message=alert.message,
                            notification_metadata={
                                "service_id": result.service_id,
                                "status": result.status,
                                "category": result.category,
                                "severity": rule.severity,
                            },
                        )
                    except Exception as err:
                        logger.warning("Failed to create in-app notification for superuser %s: %s", su.id, err)

            if "email" in channels:
                from app.alerts.engine.notify import _send_email_smtp
                from app.config import config

                if config.SMTP_HOST:
                    subject = f"[ALERT - {rule.severity.upper()}] Third-Party Health: {result.service_name}"
                    body = f"Service: {result.service_name} ({result.service_id})\nStatus: {result.status}\nError: {result.last_error or 'None'}\n\nMessage: {alert.message}"
                    for su in superusers:
                        if su.email:
                            try:
                                await asyncio.to_thread(_send_email_smtp, su.email, subject, body)
                            except Exception as err:
                                logger.warning("Failed to dispatch email alert to %s: %s", su.email, err)
                else:
                    logger.warning("Email channel requested for health alert but SMTP_HOST is not configured")

            if "telegram" in channels:
                # Telegram dispatch for platform admin alerts
                logger.info("Telegram channel selected for health alert (admin alert dispatch)")

        except Exception as exc:
            logger.warning("Error during alert dispatch: %s", exc)

    @classmethod
    async def acknowledge_alert(
        cls,
        session: AsyncSession,
        alert_id: int,
        acknowledged_by: UUID | None = None,
        duration_minutes: int = 60,
    ) -> AdminHealthAlert | None:
        """Acknowledge an open alert, snoozing notifications and banner display."""
        stmt = select(AdminHealthAlert).where(AdminHealthAlert.id == alert_id)
        res = await session.execute(stmt)
        alert = res.scalar_one_or_none()
        if not alert:
            return None

        now = datetime.now(UTC)
        until = now + timedelta(minutes=duration_minutes)
        alert.status = "acknowledged"
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_until = until
        alert.updated_at = now

        # Also update the corresponding admin_health_status record
        status_stmt = select(AdminHealthStatus).where(AdminHealthStatus.service_id == alert.service_id)
        status_res = await session.execute(status_stmt)
        status_rec = status_res.scalar_one_or_none()
        if status_rec:
            status_rec.acknowledged_until = until
            status_rec.updated_at = now

        await session.commit()
        await session.refresh(alert)
        return alert

    @classmethod
    async def get_active_alerts(cls, session: AsyncSession) -> list[AdminHealthAlert]:
        """Return active open alerts (excluding snoozed acknowledged alerts)."""
        now = datetime.now(UTC)
        stmt = (
            select(AdminHealthAlert)
            .where(
                AdminHealthAlert.status.in_(["open", "acknowledged"]),
                (AdminHealthAlert.acknowledged_until.is_(None) | (AdminHealthAlert.acknowledged_until < now)),
            )
            .order_by(AdminHealthAlert.triggered_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
