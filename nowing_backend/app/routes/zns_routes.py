"""REST routes for Zalo OA Webhook (Fast-ACK) and ZNS Template Messaging Hub (Story 23.2 / INV-23.7, INV-23.8, INV-23.9)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, ZaloConnection, ZaloMessageLog, get_async_session
from app.gateway.zalo.tasks import process_zalo_inbox_event
from app.gateway.zalo.webhook import check_timestamp_freshness, verify_zalo_signature
from app.gateway.zalo.zns_client import (
    ZnsClient,
    ZnsDncViolationError,
    ZnsQuotaExceededError,
    ZnsTimeWindowViolationError,
)
from app.schemas.zns import (
    ZnsLogItem,
    ZnsSendRequest,
    ZnsSendResponse,
    ZnsTemplateResponse,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["zns"])


# ---------------------------------------------------------------------------
# 1. Fast-ACK Inbound Webhook (AC-1, INV-23.7, INV-23.8)
# ---------------------------------------------------------------------------


@router.post(
    "/gateways/zalo/webhook",
    summary="Fast ACK & Replay-Resistant Zalo OA Webhook Receiver",
)
async def zalo_oa_fast_webhook(
    workspace_id: int,
    request: Request,
    x_zalo_signature: str | None = Header(default=None, alias="X-Zalo-Signature"),
    x_zevent_signature: str | None = Header(default=None, alias="X-ZEvent-Signature"),
    x_zalo_timestamp: str | None = Header(default=None, alias="X-Zalo-Timestamp"),
    mac: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Extract raw_body before JSON parsing, verify HMAC-SHA256 & replay freshness, return HTTP 200 < 100ms."""
    raw_body = await request.body()
    try:
        data = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    sig = x_zalo_signature or x_zevent_signature or mac or ""
    ts = x_zalo_timestamp or data.get("timestamp") or ""

    # Check timestamp presence & anti-replay (SEC-02)
    if not ts:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook timestamp header or payload",
        )
    if not check_timestamp_freshness(ts, max_drift_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook timestamp outside 300s freshness window (replay defense)",
        )

    # Resolve OA secret for workspace
    connection = None
    try:
        conn_stmt = select(ZaloConnection).where(
            ZaloConnection.workspace_id == workspace_id,
            ZaloConnection.is_active.is_(True),
        )
        res = await session.execute(conn_stmt)
        connection = res.scalar_one_or_none()
    except Exception as exc:
        logger.debug("[ZaloWebhook] Connection DB lookup note: %s", exc)

    secret = (connection.webhook_secret if connection else None) or getattr(
        config, "ZALO_WEBHOOK_SECRET", None
    )
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Zalo webhook secret not configured",
        )

    if not verify_zalo_signature(
        app_id=str(data.get("app_id") or ""),
        raw_body=raw_body,
        timestamp=ts,
        signature=sig,
        secret=secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature",
        )

    # Fast ACK: Dispatch processing to background Celery task (INV-23.8)
    try:
        process_zalo_inbox_event.delay(workspace_id, data)
    except Exception as exc:
        logger.warning("[ZaloWebhook] Celery dispatch note: %s", exc)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. ZNS Template Management & Sending (AC-2, AC-4)
# ---------------------------------------------------------------------------


@router.get(
    "/zns/templates",
    response_model=list[ZnsTemplateResponse],
    summary="List approved ZNS templates for workspace",
)
async def list_zns_templates(
    workspace_id: int,
    auth_ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    await check_permission(auth_ctx, workspace_id, Permission.VIEW_WORKSPACE, session)
    client = ZnsClient()
    return await client.get_approved_templates(session, workspace_id)


@router.post(
    "/zns/send",
    response_model=ZnsSendResponse,
    summary="Send ZNS template message with quota debit, DNC check, and time window validation",
)
async def send_zns_message(
    workspace_id: int,
    payload: ZnsSendRequest,
    auth_ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    await check_permission(auth_ctx, workspace_id, Permission.MANAGE_WORKSPACE, session)
    client = ZnsClient()

    try:
        return await client.send_zns_template(
            session=session,
            workspace_id=workspace_id,
            phone=payload.phone,
            template_id=payload.template_id,
            template_data=payload.template_data,
            user_id=auth_ctx.user_id,
            lead_id=payload.lead_id,
        )
    except ZnsTimeWindowViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ZnsDncViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ZnsQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(exc),
        ) from exc


@router.get(
    "/zns/logs",
    response_model=list[ZnsLogItem],
    summary="List sent ZNS message logs and statuses",
)
async def list_zns_logs(
    workspace_id: int,
    auth_ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[ZaloMessageLog]:
    await check_permission(auth_ctx, workspace_id, Permission.VIEW_WORKSPACE, session)
    stmt = (
        select(ZaloMessageLog)
        .where(
            ZaloMessageLog.workspace_id == workspace_id,
            ZaloMessageLog.message_type == "zns_template",
        )
        .order_by(desc(ZaloMessageLog.created_at))
        .limit(100)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())
