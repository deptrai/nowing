"""Celery maintenance tasks for external chat surfaces."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update

from app.celery_app import celery_app
from app.db import (
    ExternalChatAccount,
    ExternalChatBinding,
    ExternalChatEventStatus,
    ExternalChatHealthStatus,
    ExternalChatInboundEvent,
    ExternalChatPlatform,
    Workspace,
    WorkspaceMembership,
)
from app.gateway.inbox import persist_inbound_event, telegram_event_dedupe_key
from app.gateway.registry import resolve_platform_bundle
from app.gateway.telegram.adapter import TelegramAdapter
from app.observability.metrics import (
    record_gateway_health_check_failure,
    record_gateway_inbound_reconciled,
)
from app.services.auto_reply_agent import AutoReplyAgent
from app.services.inbound_debounce_service import InboundDebounceService
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="gateway.process_inbound_event")
def process_inbound_event_task(inbox_id: int) -> None:
    logger.warning(
        "Ignoring gateway.process_inbound_event for inbox_id=%s; "
        "FastAPI owns external chat agent turn processing.",
        inbox_id,
    )
    return None


@celery_app.task(name="gateway.reconcile_inbox")
def reconcile_inbox_task() -> None:
    async def _run() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            stale_threshold = datetime.now(UTC) - timedelta(minutes=10)
            result = await session.execute(
                update(ExternalChatInboundEvent)
                .where(
                    ExternalChatInboundEvent.status
                    == ExternalChatEventStatus.PROCESSING,
                    ExternalChatInboundEvent.received_at < stale_threshold,
                )
                .values(
                    status=ExternalChatEventStatus.RECEIVED,
                    last_error="stale processing reset for FastAPI inbox worker",
                )
            )
            for _ in range(result.rowcount or 0):
                record_gateway_inbound_reconciled(reason="stale_processing_reset")
            await session.commit()

    return run_async_celery_task(_run)


@celery_app.task(name="gateway.health_check")
def gateway_health_check_task() -> None:
    async def _run() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            result = await session.execute(select(ExternalChatAccount))
            accounts = list(result.scalars())
            for account in accounts:
                try:
                    bundle = resolve_platform_bundle(account)
                    metadata = await bundle.adapter.validate_credentials()
                    account.health_status = ExternalChatHealthStatus.OK
                    if account.platform == ExternalChatPlatform.TELEGRAM:
                        account.bot_username = metadata.get("username")
                    elif account.platform == ExternalChatPlatform.WHATSAPP:
                        cursor_state = dict(account.cursor_state or {})
                        for key in (
                            "quality_rating",
                            "account_review_status",
                            "status",
                        ):
                            if key in metadata:
                                cursor_state[key] = metadata[key]
                        account.cursor_state = cursor_state
                    elif account.platform == ExternalChatPlatform.SLACK:
                        cursor_state = dict(account.cursor_state or {})
                        for key in ("team_id", "team", "bot_user_id", "bot_username"):
                            if key in metadata:
                                cursor_state[key] = metadata[key]
                        account.cursor_state = cursor_state
                        account.bot_username = metadata.get("bot_username")
                    elif account.platform == ExternalChatPlatform.DISCORD:
                        cursor_state = dict(account.cursor_state or {})
                        for key in ("bot_user_id", "bot_username", "global_name"):
                            if key in metadata:
                                cursor_state[key] = metadata[key]
                        account.cursor_state = cursor_state
                        account.bot_username = metadata.get("bot_username")
                except Exception:
                    logger.warning(
                        "External chat health check failed platform=%s account_id=%s",
                        account.platform.value,
                        account.id,
                        exc_info=True,
                    )
                    account.health_status = ExternalChatHealthStatus.FAILING
                    record_gateway_health_check_failure(platform=account.platform.value)
                account.last_health_check_at = datetime.now(UTC)
            await session.commit()

    return run_async_celery_task(_run)


@celery_app.task(name="gateway.enqueue_received_sweep")
def enqueue_received_sweep_task() -> int:
    logger.info(
        "Skipping gateway.enqueue_received_sweep; "
        "FastAPI inbox worker scans RECEIVED rows directly."
    )
    return 0


@celery_app.task(name="gateway.retention_sweep")
def gateway_retention_sweep_task() -> None:
    async def _run() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            raw_cutoff = datetime.now(UTC) - timedelta(days=30)
            delete_cutoff = datetime.now(UTC) - timedelta(days=365)
            await session.execute(
                update(ExternalChatInboundEvent)
                .where(ExternalChatInboundEvent.received_at < raw_cutoff)
                .values(raw_payload=None)
            )
            result = await session.execute(
                select(ExternalChatInboundEvent).where(
                    ExternalChatInboundEvent.received_at < delete_cutoff
                )
            )
            for event in result.scalars():
                await session.delete(event)
            await session.commit()

    return run_async_celery_task(_run)


async def enqueue_telegram_update(account_id: int, raw_update: dict) -> int | None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        parsed = TelegramAdapter("placeholder").parse_inbound(raw_update)
        inbox_id = await persist_inbound_event(
            session,
            account_id=account_id,
            platform=ExternalChatPlatform.TELEGRAM,
            event_dedupe_key=telegram_event_dedupe_key(raw_update["update_id"]),
            external_event_id=str(raw_update["update_id"]),
            external_message_id=parsed.external_message_id,
            event_kind=parsed.event_kind,
            raw_payload=raw_update,
        )
        await session.commit()
        return inbox_id


@celery_app.task(name="gateway.process_auto_reply_buffer")
def process_auto_reply_buffer_task(
    channel: str,
    sender_id: str,
    workspace_id: int,
    thread_id: str,
    account_id: int,
    binding_id: int,
) -> dict[str, Any]:
    """3s debounce flush + RAG auto-reply + hot-lead alert dispatch."""

    async def _run() -> dict[str, Any]:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            debounce = InboundDebounceService()
            aggregated = await debounce.flush_and_aggregate_messages(channel, sender_id)
            if not aggregated:
                return {"status": "noop", "reason": "empty_buffer"}

            workspace = await session.get(Workspace, workspace_id)
            if workspace is None or not workspace.auto_reply_enabled:
                return {"status": "noop", "reason": "auto_reply_disabled"}

            # Resolve a billing user for token usage attribution.
            user_id = None
            if workspace.user_id:
                user_id = workspace.user_id
            else:
                owner_membership = await session.execute(
                    select(WorkspaceMembership)
                    .where(
                        WorkspaceMembership.workspace_id == workspace_id,
                        WorkspaceMembership.is_owner.is_(True),
                    )
                    .limit(1)
                )
                owner = owner_membership.scalars().first()
                if owner is not None:
                    user_id = owner.user_id

            binding = await session.get(ExternalChatBinding, binding_id)
            account = await session.get(ExternalChatAccount, account_id) if binding else None
            adapter = None
            if account is not None:
                try:
                    bundle = resolve_platform_bundle(account)
                    adapter = bundle.adapter
                except Exception as e:
                    logger.warning("Could not resolve platform bundle for auto-reply: %s", e)

            agent = AutoReplyAgent()
            result = await agent.generate_reply(
                workspace_id=workspace_id,
                channel=channel,
                sender_id=sender_id,
                text=aggregated,
                thread_id=thread_id,
                session=session,
                user_id=user_id,
                fallback_text=workspace.auto_reply_fallback or None,
            )

            # Send reply back to the channel if we have an adapter.
            if result.is_answered and adapter is not None and binding is not None:
                try:
                    target_peer = binding.external_peer_id or sender_id
                    await adapter.send_message(
                        external_peer_id=target_peer,
                        text=result.reply_text,
                    )
                    logger.info(
                        "Auto-reply sent for workspace=%s channel=%s sender=%s",
                        workspace_id,
                        channel,
                        sender_id,
                    )
                except Exception as e:
                    logger.error("Failed to send auto-reply: %s", e, exc_info=True)

            # Commit token usage and any lead updates staged by the agent.
            await session.commit()

            return {
                "status": "replied" if result.is_answered else "paused",
                "is_fallback": result.is_fallback,
                "is_hot_intent": result.is_hot_intent,
                "intent_reason": result.intent_reason,
                "reply_text": result.reply_text,
            }

    return run_async_celery_task(_run)
