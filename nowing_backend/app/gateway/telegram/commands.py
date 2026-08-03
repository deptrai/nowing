"""Telegram command handlers."""

from __future__ import annotations

import logging
import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.auth.context import AuthContext
from app.automations.dispatch.errors import DispatchError
from app.automations.dispatch.launch import launch_run
from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.config import config
from app.db import ExternalChatBinding, Permission, User
from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.base.commands import BaseGatewayCommands
from app.gateway.pairing import redeem_pairing_code
from app.gateway.ratelimit import acquire_token
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.telegram.callbacks import handle_callback_query
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Nowing Telegram commands:\n"
    "/start <code> - pair this chat\n"
    "/new - start a fresh conversation\n"
    "/status - latest automation run in this workspace\n"
    "/run [name] - run an automation or list active automations\n"
    "/help - show this help"
)

TELEGRAM_MESSAGE_LIMIT = 4096


async def handle_start_command(
    *,
    session,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
) -> bool:
    text = event.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not event.external_peer_id:
        await adapter.send_message(
            external_peer_id=event.external_peer_id or "",
            text="Generate a pairing code in Nowing Settings > Messaging Channels, then send /start CODE here.",
        )
        return True

    binding = await redeem_pairing_code(
        session,
        code=parts[1].strip(),
        external_peer_id=event.external_peer_id,
        external_peer_kind=event.external_peer_kind,
        external_display_name=event.display_name,
        external_username=event.username,
        external_metadata=event.metadata,
    )
    if binding is None:
        await adapter.send_message(
            external_peer_id=event.external_peer_id,
            text="That pairing code is invalid or expired. Generate a new code in Nowing.",
        )
        return True

    await adapter.send_message(
        external_peer_id=event.external_peer_id,
        text="Nowing is connected. Send a message here to chat with your agent.",
    )
    return True


async def handle_help_command(
    *, adapter: TelegramAdapter, event: ParsedInboundEvent
) -> bool:
    if not event.external_peer_id:
        return True
    await adapter.send_message(external_peer_id=event.external_peer_id, text=HELP_TEXT)
    return True


async def send_unbound_onboarding(
    *,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    dashboard_url: str,
) -> None:
    if not event.external_peer_id:
        return
    wait_ms = await acquire_token(
        f"tg:onboarded:{event.external_peer_id}",
        capacity=1,
        refill_per_sec=1 / 3600,
    )
    if wait_ms > 0:
        return
    await adapter.send_message(
        external_peer_id=event.external_peer_id,
        text=(
            "Hi! To use Nowing via Telegram, generate a pairing code at "
            f"{dashboard_url} and send /start CODE here."
        ),
    )


def _dashboard_run_url(workspace_id: int, automation_id: int, run_id: int) -> str:
    base = (config.NEXT_FRONTEND_URL or "").rstrip("/")
    return f"{base}/workspaces/{workspace_id}/automations/{automation_id}/runs/{run_id}"


def _format_run_summary(run: AutomationRun, automation: Automation | None) -> str:
    finished_at = ""
    if run.finished_at:
        finished_at = f"\nFinished: {run.finished_at.isoformat()}"
    if automation is None:
        return (
            f"A recent run exists, but the automation record is missing.\n"
            f"Run status: {run.status.value}{finished_at}\n"
            f"Run ID: {run.id}"
        )
    return (
        f"Run: {automation.name}\n"
        f"Status: {run.status.value}{finished_at}\n"
        f"Link: {_dashboard_run_url(automation.workspace_id, automation.id, run.id)}"
    )


async def _load_user(session, user_id: UUID | None) -> User | None:
    if user_id is None:
        return None
    return await session.get(User, user_id)


async def _auth_for_binding(session, binding: ExternalChatBinding) -> AuthContext:
    user = await _load_user(session, binding.user_id)
    if user is None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: user not found",
        )
    return AuthContext.session(user)


async def _latest_run_for_workspace(
    session, workspace_id: int
) -> tuple[AutomationRun, Automation | None] | None:
    result = await session.execute(
        select(AutomationRun)
        .outerjoin(Automation, Automation.id == AutomationRun.automation_id)
        .where(
            or_(
                Automation.workspace_id == workspace_id,
                Automation.id.is_(None),
            )
        )
        .order_by(AutomationRun.created_at.desc())
        .limit(1)
    )
    run = result.scalars().first()
    if run is None:
        return None
    automation = await session.get(Automation, run.automation_id)
    return run, automation


async def _active_automations_for_workspace(
    session, workspace_id: int
) -> list[Automation]:
    result = await session.execute(
        select(Automation)
        .where(
            Automation.workspace_id == workspace_id,
            Automation.status == AutomationStatus.ACTIVE,
        )
        .order_by(Automation.name)
        .limit(100)
    )
    return list(result.scalars().all())


async def _find_active_automation_by_name(
    session, workspace_id: int, name: str
) -> Automation | None:
    result = await session.execute(
        select(Automation).where(
            Automation.workspace_id == workspace_id,
            Automation.name == name,
            Automation.status == AutomationStatus.ACTIVE,
        )
    )
    return result.scalars().first()


def _strip_bot_mention(text: str) -> str:
    """Strip a leading '@BotName' (and any following whitespace) from an argument."""
    return re.sub(r"^@\S+\s*", "", text)


async def _safe_send_message(
    adapter: TelegramAdapter, external_peer_id: str, text: str
) -> None:
    """Send a Telegram reply and swallow transient send errors."""
    try:
        await adapter.send_message(external_peer_id=external_peer_id, text=text)
    except Exception:
        logger.exception("Failed to send Telegram message to %s", external_peer_id)


def _build_automation_list_text(automations: list[Automation]) -> str:
    """Build a '/run' list reply, truncating if it would exceed Telegram's message limit."""
    header = "Active automations:\n"
    footer = "\n\nSend /run <name> to start one."
    note = "\n\n... list truncated, send /run <name> for a specific automation."

    # Cap each name so one giant automation name cannot dominate the message and
    # so we do not build a huge intermediate string. The query already limits rows.
    max_body = TELEGRAM_MESSAGE_LIMIT - len(header) - len(note) - len(footer)
    max_name_len = max(max_body - 2, 0)

    included: list[str] = []
    body_len = 0
    for automation in automations:
        name = automation.name[:max_name_len]
        item = f"- {name}"
        item_len = len(item)
        if included:
            item_len += 1  # newline separator
        if body_len + item_len > max_body:
            return header + "\n".join(included) + note + footer
        body_len += item_len
        included.append(item)

    if not included:
        return header + "\nNo active automations." + footer
    return header + "\n".join(included) + footer


async def _handle_status_command(
    *,
    session,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    binding: ExternalChatBinding,
) -> bool:
    if not event.external_peer_id:
        return True

    try:
        auth = await _auth_for_binding(session, binding)
        await check_permission(
            session,
            auth,
            binding.workspace_id,
            Permission.AUTOMATIONS_READ.value,
            "You don't have permission to read automations in this workspace",
        )
    except HTTPException:
        await _safe_send_message(
            adapter,
            event.external_peer_id,
            "Access denied: you can't view runs in this workspace.",
        )
        return True

    pair = await _latest_run_for_workspace(session, binding.workspace_id)
    if pair is None:
        await _safe_send_message(
            adapter,
            event.external_peer_id,
            "No recent runs in this workspace.",
        )
        return True

    run, automation = pair
    await _safe_send_message(
        adapter,
        event.external_peer_id,
        _format_run_summary(run, automation),
    )
    return True


async def _handle_run_command(
    *,
    session,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    binding: ExternalChatBinding,
) -> bool:
    if not event.external_peer_id:
        return True

    text = event.text or ""
    parts = text.split(maxsplit=1)
    is_list = len(parts) == 1
    name = ""
    if not is_list:
        name = _strip_bot_mention(parts[1].strip())
    if not name:
        is_list = True

    try:
        auth = await _auth_for_binding(session, binding)
        await check_permission(
            session,
            auth,
            binding.workspace_id,
            Permission.AUTOMATIONS_EXECUTE.value,
            "You don't have permission to run automations in this workspace",
        )
    except HTTPException:
        await _safe_send_message(
            adapter,
            event.external_peer_id,
            "Access denied: you can't run automations in this workspace.",
        )
        return True

    if is_list:
        automations = await _active_automations_for_workspace(
            session, binding.workspace_id
        )
        if not automations:
            await _safe_send_message(
                adapter,
                event.external_peer_id,
                "No active automations in this workspace.",
            )
            return True
        await _safe_send_message(
            adapter,
            event.external_peer_id,
            _build_automation_list_text(automations),
        )
        return True

    automation = await _find_active_automation_by_name(
        session, binding.workspace_id, name
    )
    if automation is None:
        await _safe_send_message(
            adapter,
            event.external_peer_id,
            f"Automation '{name}' not found.",
        )
        return True

    trigger = AutomationTrigger(
        automation_id=automation.id,
        type=TriggerType.MANUAL,
        params={},
        static_inputs={},
    )
    try:
        await launch_run(
            session=session,
            trigger=trigger,
            runtime_inputs={"fired_by": "telegram"},
        )
    except DispatchError:
        logger.exception("DispatchError starting run for automation %s", automation.id)
        await _safe_send_message(
            adapter,
            event.external_peer_id,
            "Could not start run. Please try again later.",
        )
        return True
    except Exception:
        logger.exception(
            "Unexpected error starting run for automation %s", automation.id
        )
        await _safe_send_message(
            adapter,
            event.external_peer_id,
            "Could not start run. Please try again later.",
        )
        return True

    await _safe_send_message(
        adapter,
        event.external_peer_id,
        "Run started. You will be notified when it completes.",
    )
    return True


class TelegramGatewayCommands(BaseGatewayCommands):
    async def handle_start_command(
        self,
        *,
        session,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        return await handle_start_command(session=session, adapter=adapter, event=event)

    async def handle_help_command(
        self,
        *,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
    ) -> bool:
        return await handle_help_command(adapter=adapter, event=event)

    async def send_unbound_onboarding(
        self,
        *,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        dashboard_url: str,
    ) -> None:
        await send_unbound_onboarding(
            adapter=adapter,
            event=event,
            dashboard_url=dashboard_url,
        )

    async def handle_status_command(
        self,
        *,
        session,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        binding: ExternalChatBinding,
    ) -> bool:
        return await _handle_status_command(
            session=session, adapter=adapter, event=event, binding=binding
        )

    async def handle_run_command(
        self,
        *,
        session,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        binding: ExternalChatBinding,
    ) -> bool:
        return await _handle_run_command(
            session=session, adapter=adapter, event=event, binding=binding
        )

    async def handle_callback_query(
        self,
        *,
        session,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        binding: ExternalChatBinding,
    ) -> None:
        await handle_callback_query(
            session=session,
            adapter=adapter,
            event=event,
            binding=binding,
        )
