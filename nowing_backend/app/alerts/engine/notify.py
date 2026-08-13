"""Alert run notification dispatch (in-app + Telegram)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.persistence.models.alert_rule import AlertRule
from app.alerts.persistence.models.alert_snapshot import AlertSnapshot
from app.alerts.persistence.models.alert_subscription import AlertSubscription
from app.automations.services.telegram_notifications import (
    resolve_telegram_binding_for_run,
)
from app.db import WorkspaceMembership
from app.gateway.telegram.adapter import TelegramAdapter
from app.notifications.service import NotificationService
from app.observability.metrics import record_gateway_outbound

logger = logging.getLogger(__name__)


def _status_label(snapshot: AlertSnapshot) -> str:
    if snapshot.run_status == "failed":
        return "failed"
    if snapshot.run_status == "degraded":
        return "degraded"
    triggered = snapshot.new_items_count or snapshot.changed_items_count
    if triggered:
        return f"{triggered} matched items"
    return "no matches"


def _notification_title(alert_rule: AlertRule, snapshot: AlertSnapshot) -> str:
    status = _status_label(snapshot)
    return f"Alert '{alert_rule.name}' {status}"


def _notification_message(alert_rule: AlertRule, snapshot: AlertSnapshot) -> str:
    if snapshot.run_status == "failed":
        return f"Saved search '{alert_rule.name}' failed."
    if snapshot.run_status == "degraded":
        reasons = snapshot.degradation_reasons or []
        return f"Saved search '{alert_rule.name}' is degraded: {', '.join(reasons)}."
    triggered = snapshot.new_items_count or snapshot.changed_items_count
    if triggered:
        return (
            f"Saved search '{alert_rule.name}' matched "
            f"{triggered} item(s)."
            f"\nOpen: /dashboard/{alert_rule.workspace_id}/research/saved-searches/{alert_rule.id}"
        )
    return f"Saved search '{alert_rule.name}' ran — no matches."


async def _in_app(
    session: AsyncSession, alert_rule: AlertRule, snapshot: AlertSnapshot, user_id: UUID
) -> None:
    await NotificationService.create_notification(
        session=session,
        user_id=user_id,
        notification_type="alert_run_complete",
        title=_notification_title(alert_rule, snapshot),
        message=_notification_message(alert_rule, snapshot),
        workspace_id=alert_rule.workspace_id,
        notification_metadata={
            "alert_rule_id": str(alert_rule.id),
            "snapshot_id": str(snapshot.id),
            "new_items_count": snapshot.new_items_count,
            "run_status": snapshot.run_status,
            "degradation_reasons": snapshot.degradation_reasons or [],
        },
    )


async def _telegram(
    session: AsyncSession, alert_rule: AlertRule, snapshot: AlertSnapshot, user_id: UUID
) -> None:
    from app.automations.services.telegram_notifications import account_token

    binding = await resolve_telegram_binding_for_run(
        session, user_id, alert_rule.workspace_id
    )
    if binding is None or binding.external_peer_id is None:
        return

    token = account_token(binding.account)
    if not token:
        logger.warning("No token for Telegram account %s", binding.account_id)
        return

    try:
        adapter = TelegramAdapter(token)
        text = f"{_notification_title(alert_rule, snapshot)}\n\n{_notification_message(alert_rule, snapshot)}"
        await adapter.send_message(
            external_peer_id=binding.external_peer_id,
            text=text,
            parse_mode="MarkdownV2",
        )
        record_gateway_outbound(platform="telegram", kind="send", status="sent")
    except Exception:
        logger.exception(
            "Telegram notification for alert %s user %s failed", alert_rule.id, user_id
        )
        record_gateway_outbound(platform="telegram", kind="send", status="failed")


async def notify_alert_run(
    *,
    session: AsyncSession,
    alert_rule: AlertRule,
    snapshot: AlertSnapshot,
) -> None:
    """Deliver alert run notifications to all subscribed users."""
    rule_channels = alert_rule.notification_channels or []
    if not rule_channels:
        return

    subscriptions = (
        (
            await session.execute(
                select(AlertSubscription)
                .join(
                    WorkspaceMembership,
                    WorkspaceMembership.user_id == AlertSubscription.user_id,
                )
                .where(
                    AlertSubscription.alert_rule_id == alert_rule.id,
                    AlertSubscription.enabled.is_(True),
                    WorkspaceMembership.workspace_id == alert_rule.workspace_id,
                )
            )
        )
        .scalars()
        .all()
    )

    for sub in subscriptions:
        user_channels = sub.channels or rule_channels
        for channel in user_channels:
            if channel not in rule_channels:
                continue
            if channel == "in_app":
                await _in_app(session, alert_rule, snapshot, sub.user_id)
            elif channel == "telegram":
                await _telegram(session, alert_rule, snapshot, sub.user_id)
            else:
                # email and other channels deferred.
                pass
