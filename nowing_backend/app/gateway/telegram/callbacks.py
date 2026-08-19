"""Telegram inline-keyboard callback query handlers."""

from __future__ import annotations

import contextlib
import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.gateway import ratelimit
from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.telegram.adapter import TelegramAdapter
from app.services import dsh_telegram_checkpoint_service
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)


def _dashboard_run_url(workspace_id: int, automation_id: int, run_id: int) -> str:
    base = (config.NEXT_FRONTEND_URL or "").rstrip("/")
    return f"{base}/workspaces/{workspace_id}/automations/{automation_id}/runs/{run_id}"


async def _load_user(session: AsyncSession, user_id: UUID | None) -> User | None:
    if user_id is None:
        return None
    return await session.get(User, user_id)


async def _auth_for_binding(
    session: AsyncSession, binding: ExternalChatBinding
) -> AuthContext:
    user = await _load_user(session, binding.user_id)
    if user is None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: user not found",
        )
    return AuthContext.session(user)


async def _fetch_run(
    session: AsyncSession, run_id: int
) -> tuple[AutomationRun, Automation | None] | None:
    run = await session.get(AutomationRun, run_id)
    if run is None:
        return None
    automation = await session.get(Automation, run.automation_id)
    return run, automation


async def _format_run_summary(run: AutomationRun, automation: Automation | None) -> str:
    status = run.status.value
    finished_at = ""
    if run.finished_at:
        finished_at = f"\nFinished: {run.finished_at.isoformat()}"
    if automation is None:
        return (
            f"A recent run exists, but the automation record is missing.\n"
            f"Run status: {status}{finished_at}\n"
            f"Run ID: {run.id}"
        )
    return (
        f"Run: {automation.name}\n"
        f"Status: {status}{finished_at}\n"
        f"Link: {_dashboard_run_url(automation.workspace_id, automation.id, run.id)}"
    )


def _is_inline(event: ParsedInboundEvent) -> bool:
    return (event.external_peer_id or "").startswith("inline:")


async def _handle_view_run(
    *,
    session: AsyncSession,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    binding: ExternalChatBinding,
    run_id: int,
    callback_query_id: str | None,
) -> None:
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
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Access denied: you can't view runs in this workspace.",
                    show_alert=True,
                )
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )
        return

    try:
        pair = await _fetch_run(session, run_id)
        if pair is None:
            if callback_query_id:
                try:
                    await adapter.answer_callback_query(
                        callback_query_id=callback_query_id, text="Run not found."
                    )
                except Exception:
                    logger.warning(
                        "Failed to answer callback query %s",
                        callback_query_id,
                        exc_info=True,
                    )
            if not _is_inline(event):
                try:
                    await adapter.send_message(
                        external_peer_id=event.external_peer_id or "",
                        text=f"Run {run_id} not found.",
                    )
                except Exception:
                    logger.exception("Failed to send run-not-found message")
            return

        run, automation = pair
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id, text=""
                )
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )

        summary = await _format_run_summary(run, automation)
        if event.external_message_id:
            try:
                await adapter.edit_message(
                    external_peer_id=event.external_peer_id or "",
                    external_message_id=event.external_message_id,
                    text=summary,
                )
            except Exception:
                logger.exception("Failed to edit run summary")
                if _is_inline(event):
                    return
                try:
                    await adapter.send_message(
                        external_peer_id=event.external_peer_id or "",
                        text=summary,
                    )
                except Exception:
                    logger.exception("Failed to send run summary")
        elif not _is_inline(event):
            try:
                await adapter.send_message(
                    external_peer_id=event.external_peer_id or "",
                    text=summary,
                )
            except Exception:
                logger.exception("Failed to send run summary")
    except Exception:
        logger.exception("Error handling view_run:%s", run_id)
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Could not load run.",
                )
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )


async def _handle_rerun(
    *,
    session: AsyncSession,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    binding: ExternalChatBinding,
    automation_id: int,
    callback_query_id: str | None,
) -> None:
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
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Access denied: you can't run automations in this workspace.",
                    show_alert=True,
                )
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )
        return

    try:
        automation = await session.get(Automation, automation_id)
        if automation is None:
            if callback_query_id:
                try:
                    await adapter.answer_callback_query(
                        callback_query_id=callback_query_id,
                        text="Automation not found.",
                    )
                except Exception:
                    logger.warning(
                        "Failed to answer callback query %s",
                        callback_query_id,
                        exc_info=True,
                    )
            return

        if automation.status != AutomationStatus.ACTIVE:
            if callback_query_id:
                try:
                    await adapter.answer_callback_query(
                        callback_query_id=callback_query_id,
                        text=f"Automation is {automation.status.value}, not active.",
                        show_alert=True,
                    )
                except Exception:
                    logger.warning(
                        "Failed to answer callback query %s",
                        callback_query_id,
                        exc_info=True,
                    )
            return

        trigger = AutomationTrigger(
            automation_id=automation.id,
            type=TriggerType.MANUAL,
            params={},
            static_inputs={},
        )
        await launch_run(
            session=session,
            trigger=trigger,
            runtime_inputs={"fired_by": "telegram_callback"},
        )

        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Run started. You will be notified when it completes.",
                )
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )

        if _is_inline(event) and event.external_message_id:
            try:
                await adapter.edit_message(
                    external_peer_id=event.external_peer_id or "",
                    external_message_id=event.external_message_id,
                    text=f"Started run for automation '{automation.name}'.",
                )
            except Exception:
                logger.exception("Failed to edit rerun confirmation")
        else:
            try:
                await adapter.send_message(
                    external_peer_id=event.external_peer_id or "",
                    text=f"Started run for automation '{automation.name}'.",
                )
            except Exception:
                logger.exception("Failed to send rerun confirmation")
    except DispatchError:
        logger.exception("DispatchError rerunning automation %s", automation_id)
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Could not start run. Please try again later.",
                )
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )
    except Exception:
        logger.exception("Unexpected error rerunning automation %s", automation_id)
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Could not start run. Please try again later.",
                )
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )


async def _handle_dsh_callback(
    *,
    session: AsyncSession,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    binding: ExternalChatBinding,
    action: str,
    token: str,
    callback_query_id: str | None,
) -> None:
    """Handle 3-part dsh:{action}:{token} callbacks with rate limiting and RBAC."""
    # DSH checkpoint callbacks affect wallet/PII; only allow direct chats for now.
    if getattr(binding, "external_peer_kind", None) != "direct":
        if callback_query_id:
            with contextlib.suppress(Exception):
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Vui lòng mở khóa trong chat riêng với bot.",
                    show_alert=True,
                )
        return

    # Enforce clicker == card recipient (owner). In a direct chat the peer id and
    # the user id are the same; if a message is forwarded to another chat, the
    # clicker will not match and the action is rejected.
    if event.external_user_id is not None and str(event.external_user_id) != str(
        binding.external_peer_id
    ):
        if callback_query_id:
            with contextlib.suppress(Exception):
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Thao tác này chỉ dành cho người nhận card.",
                    show_alert=True,
                )
        return

    rate_limit = getattr(config, "DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE", 60)
    user_id = binding.user_id or "anonymous"
    key = f"telegram:checkpoint:{binding.workspace_id}:{user_id}"
    wait_ms = await ratelimit.acquire_token(
        key,
        capacity=rate_limit,
        refill_per_sec=rate_limit / 60.0,
    )
    if wait_ms > 0:
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Thao tác quá nhanh, vui lòng thử lại sau.",
                    show_alert=True,
                )
            except Exception:
                logger.warning(
                    "Failed to answer rate-limited callback query", exc_info=True
                )
        return

    try:
        auth = await _auth_for_binding(session, binding)
        required_perm = (
            Permission.LEADS_READ.value
            if action == "dossier"
            else Permission.LEADS_WRITE.value
        )
        await check_permission(
            session,
            auth,
            binding.workspace_id,
            required_perm,
            "You don't have permission to perform this lead action in this workspace",
        )
    except HTTPException:
        if callback_query_id:
            try:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Access denied: you don't have permission to perform this action.",
                    show_alert=True,
                )
            except Exception:
                logger.warning("Failed to answer denied callback query", exc_info=True)
        return

    checkpoint_svc = dsh_telegram_checkpoint_service.DshTelegramCheckpointService()
    try:
        if action == "unlock":
            await checkpoint_svc.handle_unlock_callback(
                session=session,
                adapter=adapter,
                event=event,
                binding=binding,
                callback_token=token,
                callback_query_id=callback_query_id,
            )
        elif action == "dossier":
            await checkpoint_svc.handle_dossier_callback(
                session=session,
                adapter=adapter,
                event=event,
                binding=binding,
                callback_token=token,
                callback_query_id=callback_query_id,
            )
        elif action == "skip":
            await checkpoint_svc.handle_skip_callback(
                session=session,
                adapter=adapter,
                event=event,
                binding=binding,
                callback_token=token,
                callback_query_id=callback_query_id,
            )
        elif action == "refund":
            await checkpoint_svc.handle_refund_callback(
                session=session,
                adapter=adapter,
                event=event,
                binding=binding,
                callback_token=token,
                callback_query_id=callback_query_id,
            )
        else:
            if callback_query_id:
                with contextlib.suppress(Exception):
                    await adapter.answer_callback_query(
                        callback_query_id=callback_query_id
                    )
    except Exception:
        logger.exception("Unexpected error handling dsh:%s callback", action)
        if callback_query_id:
            with contextlib.suppress(Exception):
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Không thể xử lý thao tác này.",
                    show_alert=True,
                )


async def handle_callback_query(
    *,
    session: AsyncSession,
    adapter: TelegramAdapter,
    event: ParsedInboundEvent,
    binding: ExternalChatBinding,
) -> None:
    """Dispatch a Telegram ``callback_query`` to ``view_run:``, ``rerun:``, or ``dsh:`` handlers."""
    data = event.text or ""
    callback_query_id = (event.metadata or {}).get("callback_query_id")

    if not data:
        if callback_query_id:
            try:
                await adapter.answer_callback_query(callback_query_id=callback_query_id)
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )
        return

    if not event.external_peer_id:
        if callback_query_id:
            try:
                await adapter.answer_callback_query(callback_query_id=callback_query_id)
            except Exception:
                logger.warning(
                    "Failed to answer callback query %s",
                    callback_query_id,
                    exc_info=True,
                )
        return

    # Check 3-part dsh:{action}:{token} callback
    if data.startswith("dsh:"):
        dsh_parts = data.split(":", 2)
        if len(dsh_parts) != 3:
            if callback_query_id:
                with contextlib.suppress(Exception):
                    await adapter.answer_callback_query(
                        callback_query_id=callback_query_id,
                        text="Dữ liệu callback không hợp lệ.",
                        show_alert=True,
                    )
            return
        _, action, token = dsh_parts
        await _handle_dsh_callback(
            session=session,
            adapter=adapter,
            event=event,
            binding=binding,
            action=action,
            token=token,
            callback_query_id=callback_query_id,
        )
        return

    parts = data.split(":", 1)
    prefix = parts[0]
    item_id: int | None = None
    if len(parts) > 1 and parts[1].isdigit():
        item_id = int(parts[1])

    if prefix == "view_run" and item_id is not None:
        await _handle_view_run(
            session=session,
            adapter=adapter,
            event=event,
            binding=binding,
            run_id=item_id,
            callback_query_id=callback_query_id,
        )
        return

    if prefix == "rerun" and item_id is not None:
        await _handle_rerun(
            session=session,
            adapter=adapter,
            event=event,
            binding=binding,
            automation_id=item_id,
            callback_query_id=callback_query_id,
        )
        return

    # Unknown callback data: answer to clear the spinner and let the chat path handle it.
    if callback_query_id:
        try:
            await adapter.answer_callback_query(callback_query_id=callback_query_id)
        except Exception:
            logger.warning(
                "Failed to answer callback query %s", callback_query_id, exc_info=True
            )
