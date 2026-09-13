"""Messaging gateway routes."""

from __future__ import annotations

import hmac
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, Response

from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatPlatform,
    get_async_session,
)
from app.gateway.accounts import (
    get_slack_account_by_team,
)
from app.gateway.inbox import (
    persist_inbound_event,
    slack_event_dedupe_key,
    telegram_event_dedupe_key,
)
from app.observability.metrics import (
    record_gateway_inbox_write,
    record_gateway_webhook_parse_error,
)

from ._helpers import (
    _classify_telegram_event,
    _slack_event_kind,
    _slack_gateway_enabled,
    _telegram_gateway_enabled,
    _telegram_message,
    verify_slack_signature,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks/slack")
async def slack_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    if not _slack_gateway_enabled():
        return Response(status_code=200)

    body = await request.body()
    if not verify_slack_signature(
        signing_secret=config.GATEWAY_SLACK_SIGNING_SECRET or "",
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
        body=body,
    ):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    try:
        payload = json.loads(body.decode())
    except ValueError:
        record_gateway_webhook_parse_error()
        return Response(status_code=200)

    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload.get("challenge", "")})
    if payload.get("type") != "event_callback":
        return Response(status_code=200)

    event = payload.get("event") or {}
    event_id = payload.get("event_id")
    team_id = payload.get("team_id") or event.get("team")
    if not event_id or not team_id:
        return Response(status_code=200)

    account = await get_slack_account_by_team(session, team_id=str(team_id))
    if account is None:
        logger.warning("Ignoring Slack event for uninstalled team_id=%s", team_id)
        return Response(status_code=200)

    bot_user_id = (account.cursor_state or {}).get("bot_user_id")
    if event.get("bot_id") or (bot_user_id and event.get("user") == bot_user_id):
        return Response(status_code=200)

    try:
        inbox_id = await persist_inbound_event(
            session,
            account_id=account.id,
            platform=ExternalChatPlatform.SLACK,
            event_dedupe_key=slack_event_dedupe_key(event_id),
            external_event_id=str(event_id),
            external_message_id=str(event.get("ts")) if event.get("ts") else None,
            event_kind=_slack_event_kind(payload),
            raw_payload=payload,
            request_id=f"gateway_{uuid.uuid4().hex[:16]}",
        )
        await session.commit()
        record_gateway_inbox_write(platform="slack", dedup_skipped=inbox_id is None)
    except Exception:  # rollback on slack webhook persistence failure
        await session.rollback()
        logger.exception("Slack webhook persistence failed team_id=%s", team_id)
    return Response(status_code=200)


async def _resolve_webhook_account(
    session: AsyncSession,
    *,
    account_id: int,
    header_secret: str | None,
) -> ExternalChatAccount:
    account = await session.get(ExternalChatAccount, account_id)
    if account is None or account.platform != ExternalChatPlatform.TELEGRAM:
        raise HTTPException(status_code=404, detail="Gateway account not found")
    expected_secret = account.webhook_secret or ""
    if not expected_secret or not hmac.compare_digest(
        header_secret or "", expected_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    return account


@router.post("/webhooks/telegram/{account_id}")
async def telegram_webhook(
    request: Request,
    account_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    if not _telegram_gateway_enabled():
        return Response(status_code=200)

    request_id = f"gateway_{uuid.uuid4().hex[:16]}"
    try:
        payload = await request.json()
    except ValueError:
        record_gateway_webhook_parse_error()
        return Response(status_code=200)

    account = await _resolve_webhook_account(
        session,
        account_id=account_id,
        header_secret=request.headers.get("X-Telegram-Bot-Api-Secret-Token"),
    )

    try:
        update_id = payload.get("update_id")
        if update_id is None:
            return Response(status_code=200)

        message = _telegram_message(payload) or {}
        inbox_id = await persist_inbound_event(
            session,
            account_id=account.id,
            platform=ExternalChatPlatform.TELEGRAM,
            event_dedupe_key=telegram_event_dedupe_key(update_id),
            external_event_id=str(update_id),
            external_message_id=(
                str(message["message_id"])
                if message.get("message_id") is not None
                else None
            ),
            event_kind=_classify_telegram_event(payload),
            raw_payload=payload,
            request_id=request_id,
        )
        await session.commit()
        record_gateway_inbox_write(platform="telegram", dedup_skipped=inbox_id is None)
        return Response(status_code=200)
    except Exception:  # rollback on telegram webhook persistence failure
        await session.rollback()
        logger.exception("Telegram webhook processing failed account_id=%s", account_id)
        return Response(status_code=200)
