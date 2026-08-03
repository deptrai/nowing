"""Telegram notifications for automation runs."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.runtime import repository
from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatHealthStatus,
    ExternalChatPlatform,
    User,
)
from app.gateway.accounts import account_token
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.telegram.formatting import chunk_message, escape_markdown_v2
from app.notifications.constants import TITLE_MAX_LENGTH
from app.notifications.service.facade import NotificationService
from app.observability.metrics import record_gateway_outbound

logger = logging.getLogger(__name__)

_STATUS_LABELS: dict[RunStatus, tuple[str, str]] = {
    RunStatus.SUCCEEDED: ("✅", "finished successfully"),
    RunStatus.FAILED: ("❌", "failed"),
    RunStatus.CANCELLED: ("⚠️", "cancelled"),
    RunStatus.TIMED_OUT: ("⏱", "timed out"),
}


def _status_emoji_and_label(status: RunStatus) -> tuple[str, str] | None:
    """Return the emoji and human label for a terminal run status, or None."""
    return _STATUS_LABELS.get(status)


def _format_output_text(output: Any) -> str:
    """Render a run output value as human-readable text."""
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    if isinstance(output, (list, dict)):
        try:
            return json.dumps(output, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass
    return str(output)


def _first_error_line(run_error: dict[str, Any] | None) -> str:
    """Extract the first line of a structured run error."""
    if not run_error:
        return ""
    message = (
        run_error.get("message") if isinstance(run_error, dict) else str(run_error)
    )
    if not message:
        return ""
    return str(message).splitlines()[0]


def format_automation_run_message(
    run: AutomationRun,
    automation: Automation,
    run_error: dict[str, Any] | None = None,
) -> list[str]:
    """Build a MarkdownV2 message for an automation run and chunk it for Telegram."""
    name = automation.name if automation and automation.name else "Unknown automation"
    escaped_name = escape_markdown_v2(f"'{name}'")
    status_info = _status_emoji_and_label(run.status)
    if status_info is None:
        logger.warning(
            "Cannot format message for non-terminal run status %s",
            run.status.value,
        )
        return []

    emoji, status_label = status_info
    header = f"{emoji} Automation *{escaped_name}* {escape_markdown_v2(status_label)}"
    is_success = run.status == RunStatus.SUCCEEDED

    base_url = (config.NEXT_FRONTEND_URL or "").rstrip("/")
    parts: list[str] = [header]
    if base_url:
        deep_link = (
            f"{base_url}/dashboard/{automation.workspace_id}"
            f"/automations/{automation.id}?run_id={run.id}"
        )
        parts.append(f"[Open run]({deep_link})")

    if not is_success:
        first_error = _first_error_line(run_error or run.error)
        if first_error:
            parts.append(escape_markdown_v2(first_error))
    elif run.output is not None:
        output_text = _format_output_text(run.output)
        if output_text:
            parts.append(escape_markdown_v2(output_text))

    full_text = "\n\n".join(parts)
    return chunk_message(full_text)


async def resolve_telegram_binding_for_run(
    session: AsyncSession,
    user_id: Any,
    workspace_id: int,
) -> ExternalChatBinding | None:
    """Return the most recently created bound Telegram binding for a workspace."""
    stmt = (
        select(ExternalChatBinding)
        .join(ExternalChatAccount)
        .options(selectinload(ExternalChatBinding.account))
        .where(
            ExternalChatBinding.user_id == user_id,
            ExternalChatBinding.workspace_id == workspace_id,
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


async def send_automation_run_telegram_notification(
    session: AsyncSession,
    run_id: int,
) -> None:
    """Create an in-app notification and, if enabled, send a Telegram message."""
    run = await repository.load_run(session, run_id)
    if run is None:
        logger.warning("automation_run %d not found for notification", run_id)
        return

    automation = run.automation
    if automation is None:
        logger.warning("automation for run %d not loaded", run_id)
        return

    if automation.created_by_user_id is None:
        logger.warning(
            "automation %d has no creator; skipping notification", automation.id
        )
        return

    user = await session.get(User, automation.created_by_user_id)
    if user is None:
        logger.warning(
            "creator %s for automation %d not found",
            automation.created_by_user_id,
            automation.id,
        )
        return

    status_info = _status_emoji_and_label(run.status)
    if status_info is None:
        logger.warning(
            "Run %d has non-terminal status %s; skipping notification",
            run.id,
            run.status.value,
        )
        return

    _, status_label = status_info
    title = f"Automation '{automation.name}' {status_label}"[:TITLE_MAX_LENGTH]

    await NotificationService.create_notification(
        session=session,
        user_id=user.id,
        notification_type="automation_run_complete",
        title=title,
        message=title,
        workspace_id=automation.workspace_id,
        notification_metadata={
            "workspace_id": automation.workspace_id,
            "run_id": run.id,
            "automation_id": automation.id,
            "status": run.status.value,
        },
    )

    preferences = user.notification_preferences or {}
    automation_run_complete = preferences.get("automation_run_complete")
    if (
        not isinstance(automation_run_complete, dict)
        or automation_run_complete.get("telegram") is not True
    ):
        return

    binding = await resolve_telegram_binding_for_run(
        session, user.id, automation.workspace_id
    )
    if binding is None:
        logger.info(
            "No active Telegram binding for user %s workspace %s",
            user.id,
            automation.workspace_id,
        )
        return

    token = account_token(binding.account)
    if not token:
        logger.warning("No token available for Telegram account %s", binding.account_id)
        return

    if not binding.external_peer_id:
        logger.warning("Telegram binding %s has no peer id", binding.id)
        return

    try:
        chunks = format_automation_run_message(
            run,
            automation,
            run_error=run.error if run.status != RunStatus.SUCCEEDED else None,
        )
        adapter = TelegramAdapter(token)
        for chunk in chunks:
            await adapter.send_message(
                external_peer_id=binding.external_peer_id,
                text=chunk,
                parse_mode="MarkdownV2",
            )
        record_gateway_outbound(platform="telegram", kind="send", status="sent")
    except Exception:
        logger.exception("Failed to send Telegram notification for run %d", run_id)
        record_gateway_outbound(platform="telegram", kind="send", status="failed")
