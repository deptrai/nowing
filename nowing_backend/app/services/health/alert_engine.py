"""Health Alert Engine for evaluating threshold rules, deduplicating, and dispatching alerts."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import User
from app.db.enums import (
    ExternalChatBindingState,
    ExternalChatHealthStatus,
    ExternalChatPlatform,
)
from app.models.admin_health import (
    AdminHealthAlert,
    AdminHealthAlertRule,
    AdminHealthHistory,
    AdminHealthStatus,
)
from app.models.chat import ExternalChatAccount, ExternalChatBinding
from app.notifications.service.facade import NotificationService
from app.services.health.probe_base import HealthResult

logger = logging.getLogger(__name__)


class AdminHealthAlertEngine:
    """Evaluates probe results against health alert rules, dedupes, and emits incidents."""

    # Default rules used when the database table is empty or until migrations run.
    DEFAULT_RULES: list[dict[str, Any]] = [
        {
            "name": "Core infra unavailable",
            "category": "infra",
            "service_id_pattern": None,
            "condition_json": {"status": "unavailable", "consecutive_probes": 1},
            "severity": "critical",
            "channels": ["in_app", "email"],
            "cooldown_minutes": 15,
            "enabled": True,
        },
        {
            "name": "LLM/AI model dead",
            "category": "model",
            "service_id_pattern": None,
            "condition_json": {"status": "unavailable", "consecutive_probes": 2},
            "severity": "high",
            "channels": ["in_app", "email"],
            "cooldown_minutes": 15,
            "enabled": True,
        },
        {
            "name": "Scraper degraded",
            "category": "scraper",
            "service_id_pattern": None,
            "condition_json": {"metric": "success_rate_15m", "op": "<", "threshold": 50.0},
            "severity": "medium",
            "channels": ["in_app"],
            "cooldown_minutes": 15,
            "enabled": True,
        },
        {
            "name": "Proxy dead",
            "category": "proxy",
            "service_id_pattern": None,
            "condition_json": {"status": "unavailable", "consecutive_probes": 1},
            "severity": "high",
            "channels": ["in_app", "email"],
            "cooldown_minutes": 15,
            "enabled": True,
        },
        {
            "name": "ChainLens research degraded",
            "category": "research",
            "service_id_pattern": None,
            "condition_json": {"status_not": "healthy", "consecutive_probes": 2},
            "severity": "medium",
            "channels": ["in_app"],
            "cooldown_minutes": 15,
            "enabled": True,
        },
    ]

    @classmethod
    async def evaluate_result(
        cls,
        session: AsyncSession,
        result: HealthResult,
    ) -> list[AdminHealthAlert]:
        """Evaluate a single probe result against matching active rules."""
        now = datetime.now(UTC)

        # 1. Auto-resolve logic: if result is healthy, resolve open alerts for this service.
        #    Requires 2 consecutive healthy probes before resolving to avoid flapping.
        if result.status == "healthy":
            healthy_count = 1
            hist_stmt = (
                select(AdminHealthHistory.status)
                .where(AdminHealthHistory.service_id == result.service_id)
                .order_by(AdminHealthHistory.probe_at.desc())
                .limit(1)
            )
            hist_res = await session.execute(hist_stmt)
            past_statuses = list(hist_res.scalars().all())
            if past_statuses and past_statuses[0] == "healthy":
                healthy_count = 2

            if healthy_count >= 2:
                open_alerts_stmt = select(AdminHealthAlert).where(
                    AdminHealthAlert.service_id == result.service_id,
                    AdminHealthAlert.status.in_(["open", "acknowledged"]),
                )
                open_res = await session.execute(open_alerts_stmt)
                open_alerts = list(open_res.scalars().all())
                for oa in open_alerts:
                    oa.status = "resolved"
                    oa.resolved_at = now
                    oa.updated_at = now

                # Clear snooze on the corresponding status record
                if open_alerts:
                    status_stmt = select(AdminHealthStatus).where(
                        AdminHealthStatus.service_id == result.service_id
                    )
                    status_res = await session.execute(status_stmt)
                    status_rec = status_res.scalar_one_or_none()
                    if status_rec:
                        status_rec.acknowledged_until = None
                        status_rec.updated_at = now
                    await session.commit()
            return []

        # 2. Load rules, falling back to in-code defaults if none exist in DB.
        stmt = select(AdminHealthAlertRule).where(AdminHealthAlertRule.enabled.is_(True))
        res = await session.execute(stmt)
        rules = list(res.scalars().all())

        if not rules:
            # Hydrate ephemeral default rules when the table is empty.
            rules = [AdminHealthAlertRule(**r) for r in cls.DEFAULT_RULES]

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

            # Check deduplication & cooldown against open/acknowledged/resolved alerts
            existing_alert_stmt = select(AdminHealthAlert).where(
                AdminHealthAlert.service_id == result.service_id,
                AdminHealthAlert.rule_id == rule.id,
                AdminHealthAlert.status.in_(["open", "acknowledged"]),
            )
            existing_res = await session.execute(existing_alert_stmt)
            existing_alert = existing_res.scalar_one_or_none()

            if existing_alert is not None:
                # Re-open expired acknowledged alerts before checking cooldown
                if existing_alert.status == "acknowledged" and (
                    existing_alert.acknowledged_until is None or existing_alert.acknowledged_until < now
                ):
                    existing_alert.status = "open"
                    existing_alert.acknowledged_until = None
                    existing_alert.updated_at = now
                elif existing_alert.triggered_at and rule.cooldown_minutes and rule.cooldown_minutes > 0:
                    cooldown_end = existing_alert.triggered_at + timedelta(minutes=rule.cooldown_minutes)
                    if now < cooldown_end:
                        # Update timestamp only (no triggered_at overwrite)
                        existing_alert.updated_at = now
                        continue
                    else:
                        # Cooldown elapsed: re-open if acknowledged and treat as new incident
                        existing_alert.status = "open"
                        existing_alert.acknowledged_until = None
                        existing_alert.triggered_at = now
                        existing_alert.updated_at = now
                else:
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
            await session.flush()
            await session.refresh(alert)
            triggered_alerts.append(alert)

            # Persist the alert before attempting best-effort notification dispatch.
            # If dispatch fails, the alert row is already committed and will not be lost.
            await session.commit()

            # Dispatch notification via Generic Alert Engine
            try:
                await cls._dispatch_notification(session, rule, alert, result)
            except Exception as dispatch_exc:
                logger.warning("Notification dispatch failed for alert %s: %s", alert.id, dispatch_exc)

        if triggered_alerts:
            # Ensure any in-memory updates (e.g., existing_alert re-open) are committed
            # when no new alert was created for this rule but an existing one was touched.
            await session.commit()

        return triggered_alerts

    @staticmethod
    def validate_condition(condition_json: dict[str, Any] | None) -> dict[str, Any]:
        """Validate and normalize an alert rule condition JSON.

        Supported shapes:
        - {"status": "<status>", "consecutive_probes": 1}
        - {"status_not": "<status>", "consecutive_probes": 1}
        - {"metric": "success_rate_15m"|"error_rate_15m"|"latency_ms", "op": "<"|">"|"<="|">="|"=="|"!=", "threshold": number}

        Raises ValueError for unsupported or malformed conditions.
        """
        cond = condition_json or {}
        if not cond:
            raise ValueError("condition_json cannot be empty")

        # Status equality / inequality with optional consecutive_probes
        if "status" in cond or "status_not" in cond:
            target_status = cond.get("status") or cond.get("status_not")
            if not isinstance(target_status, str):
                raise ValueError("status/status_not must be a string")
            consecutive = cond.get("consecutive_probes", 1)
            if not isinstance(consecutive, int) or consecutive < 1:
                raise ValueError("consecutive_probes must be a positive integer")
            allowed = {"status", "status_not", "consecutive_probes"}
            if set(cond.keys()) - allowed:
                raise ValueError(f"Unsupported keys for status condition: {set(cond.keys()) - allowed}")
            return cond

        # Metric threshold
        if "metric" in cond:
            metric = cond.get("metric")
            if metric not in ("success_rate_15m", "error_rate_15m", "latency_ms"):
                raise ValueError(f"Unsupported metric: {metric}")
            op = cond.get("op")
            if op not in ("<", ">", "<=", ">=", "==", "!=", "=", "<>"):
                raise ValueError(f"Unsupported operator: {op}")
            threshold = cond.get("threshold")
            if threshold is None:
                raise ValueError("threshold is required for metric conditions")
            try:
                float(threshold)
            except (TypeError, ValueError) as exc:
                raise ValueError("threshold must be a number") from exc
            allowed = {"metric", "op", "threshold"}
            if set(cond.keys()) - allowed:
                raise ValueError(f"Unsupported keys for metric condition: {set(cond.keys()) - allowed}")
            return cond

        raise ValueError(
            "condition_json must contain one of: 'status', 'status_not', or 'metric'"
        )

    @classmethod
    async def _check_rule_condition(
        cls,
        session: AsyncSession,
        rule: AdminHealthAlertRule,
        result: HealthResult,
    ) -> bool:
        """Inspect rule condition JSON against the current and recent probe state."""
        try:
            cond = cls.validate_condition(rule.condition_json)
        except ValueError as exc:
            logger.warning("Invalid condition_json for rule %s: %s", rule.id, exc)
            return False

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
                past_statuses = list(hist_res.scalars().all())
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
                past_statuses = list(hist_res.scalars().all())
                if len(past_statuses) < consecutive_probes or any(s == status_not for s in past_statuses):
                    return False
            return True

        # 3. Metric threshold check (supports success_rate_15m, error_rate_15m, latency_ms with <, >, <=, >=, ==, !=)
        metric = cond.get("metric")
        op = cond.get("op")
        threshold = cond.get("threshold")
        if metric and op and threshold is not None:
            value: float | int | None = None
            if metric == "success_rate_15m":
                value = result.success_rate_15m
            elif metric == "error_rate_15m":
                value = result.error_rate_15m
            elif metric == "latency_ms":
                value = result.latency_ms or 0

            if value is None:
                return False

            try:
                target = float(threshold)
            except (TypeError, ValueError):
                return False

            if op == "<":
                return value < target
            elif op == ">":
                return value > target
            elif op == "<=":
                return value <= target
            elif op == ">=":
                return value >= target
            elif op in ("==", "="):
                return abs(value - target) < 1e-9
            elif op in ("!=", "<>"):
                return abs(value - target) >= 1e-9

        return False

    @classmethod
    async def _resolve_telegram_binding_for_admin(
        cls,
        session: AsyncSession,
        user_id: Any,
    ) -> ExternalChatBinding | None:
        """Return the most recently created bound Telegram binding for a user (any workspace)."""
        stmt = (
            select(ExternalChatBinding)
            .join(ExternalChatAccount)
            .options(selectinload(ExternalChatBinding.account))
            .where(
                ExternalChatBinding.user_id == user_id,
                ExternalChatBinding.state == ExternalChatBindingState.BOUND,
                ExternalChatBinding.revoked_at.is_(None),
                ExternalChatBinding.suspended_at.is_(None),
                ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
                ExternalChatAccount.suspended_at.is_(None),
                ExternalChatAccount.health_status != ExternalChatHealthStatus.FAILING,
            )
            .order_by(ExternalChatBinding.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def _dispatch_notification(
        cls,
        session: AsyncSession,
        rule: AdminHealthAlertRule,
        alert: AdminHealthAlert,
        result: HealthResult,
    ) -> None:
        """Best-effort notification dispatch to configured channels (in-app, email, telegram, slack)."""
        from app.alerts.engine.notify import _send_email_smtp
        from app.automations.services.telegram_notifications import account_token
        from app.config import config
        from app.gateway.slack.adapter import SlackAdapter
        from app.gateway.telegram.adapter import TelegramAdapter
        from app.gateway.telegram.formatting import escape_markdown_v2

        try:
            channels = rule.channels or ["in_app"]
            logger.info(
                "Dispatching admin health alert %s for service %s to channels %s",
                alert.id,
                result.service_id,
                channels,
            )

            su_stmt = select(User).where(User.is_superuser.is_(True))
            su_res = await session.execute(su_stmt)
            superusers = list(su_res.scalars().all())

            if "in_app" in channels:
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
                if config.SMTP_HOST:
                    subject = f"[ALERT - {rule.severity.upper()}] Third-Party Health: {result.service_name}"
                    body = (
                        f"Service: {result.service_name} ({result.service_id})\n"
                        f"Status: {result.status}\n"
                        f"Error: {result.last_error or 'None'}\n\n"
                        f"Message: {alert.message}"
                    )
                    for su in superusers:
                        if su.email:
                            try:
                                await asyncio.to_thread(_send_email_smtp, su.email, subject, body)
                            except Exception as err:
                                logger.warning("Failed to dispatch email alert to %s: %s", su.email, err)
                else:
                    logger.warning("Email channel requested for health alert but SMTP_HOST is not configured")

            if "telegram" in channels:
                for su in superusers:
                    try:
                        binding = await cls._resolve_telegram_binding_for_admin(session, su.id)
                        if not binding or not binding.external_peer_id:
                            continue
                        token = account_token(binding.account)
                        if not token:
                            continue
                        adapter = TelegramAdapter(token)
                        raw_text = f"[ALERT - {rule.severity.upper()}] Third-Party Health: {result.service_name}\n\n{alert.message}"
                        escaped_text = escape_markdown_v2(raw_text)
                        await adapter.send_message(
                            external_peer_id=binding.external_peer_id,
                            text=escaped_text,
                            parse_mode="MarkdownV2",
                        )
                    except Exception as err:
                        logger.warning("Failed to dispatch telegram alert for superuser %s: %s", su.id, err)

            if "slack" in channels:
                slack_bot_token = getattr(config, "SLACK_BOT_TOKEN", None)
                slack_alert_channel = getattr(config, "SLACK_ALERT_CHANNEL", None)
                if slack_bot_token and slack_alert_channel:
                    try:
                        adapter = SlackAdapter(slack_bot_token)
                        text = (
                            f"[{rule.severity.upper()}] Third-Party Health Alert\n"
                            f"Service: {result.service_name} ({result.service_id})\n"
                            f"Status: {result.status}\n"
                            f"Error: {result.last_error or 'None'}\n\n"
                            f"Message: {alert.message}"
                        )
                        await adapter.send_message(
                            external_peer_id=slack_alert_channel,
                            text=text,
                        )
                    except Exception as err:
                        logger.warning("Failed to dispatch slack alert: %s", err)
                else:
                    logger.warning(
                        "Slack channel requested for health alert but SLACK_BOT_TOKEN and/or SLACK_ALERT_CHANNEL not configured"
                    )

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

        # 404 for already-resolved alerts
        if alert.status == "resolved":
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
    async def resolve_alert(cls, session: AsyncSession, alert_id: int) -> AdminHealthAlert | None:
        """Manually resolve an active health alert."""
        stmt = select(AdminHealthAlert).where(AdminHealthAlert.id == alert_id)
        res = await session.execute(stmt)
        alert = res.scalar_one_or_none()
        if not alert:
            return None

        if alert.status == "resolved":
            return alert

        now = datetime.now(UTC)
        alert.status = "resolved"
        alert.resolved_at = now
        alert.updated_at = now

        status_stmt = select(AdminHealthStatus).where(AdminHealthStatus.service_id == alert.service_id)
        status_res = await session.execute(status_stmt)
        status_rec = status_res.scalar_one_or_none()
        if status_rec:
            status_rec.acknowledged_until = None
            status_rec.updated_at = now

        await session.commit()
        await session.refresh(alert)
        return alert

    @classmethod
    async def get_rules(
        cls,
        session: AsyncSession,
        enabled_only: bool = True,
    ) -> list[AdminHealthAlertRule]:
        """Return alert rules, optionally only enabled ones."""
        stmt = select(AdminHealthAlertRule)
        if enabled_only:
            stmt = stmt.where(AdminHealthAlertRule.enabled.is_(True))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_rule(cls, session: AsyncSession, rule_id: int) -> AdminHealthAlertRule | None:
        """Return a single alert rule by ID."""
        return await session.get(AdminHealthAlertRule, rule_id)

    @classmethod
    async def create_rule(
        cls,
        session: AsyncSession,
        rule: AdminHealthAlertRule,
    ) -> AdminHealthAlertRule:
        """Create a new alert rule."""
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    @classmethod
    async def update_rule(
        cls,
        session: AsyncSession,
        rule: AdminHealthAlertRule,
    ) -> AdminHealthAlertRule:
        """Update an existing alert rule."""
        await session.commit()
        await session.refresh(rule)
        return rule

    @classmethod
    async def delete_rule(cls, session: AsyncSession, rule_id: int) -> bool:
        """Delete an alert rule by ID."""
        rule = await session.get(AdminHealthAlertRule, rule_id)
        if not rule:
            return False
        await session.delete(rule)
        await session.commit()
        return True

    @classmethod
    async def get_active_alerts(cls, session: AsyncSession) -> list[AdminHealthAlert]:
        """Return active open alerts (excluding snoozed acknowledged alerts)."""
        now = datetime.now(UTC)

        # Re-open any acknowledged alerts whose snooze has expired
        expired_stmt = select(AdminHealthAlert).where(
            AdminHealthAlert.status == "acknowledged",
            AdminHealthAlert.acknowledged_until.isnot(None),
            AdminHealthAlert.acknowledged_until < now,
        )
        expired_res = await session.execute(expired_stmt)
        for alert in expired_res.scalars().all():
            alert.status = "open"
            alert.acknowledged_until = None
            alert.updated_at = now
        await session.commit()

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
