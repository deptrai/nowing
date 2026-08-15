"""REST routes for Assisted Zalo Outbound, ZNS Gateway, and Telegram Alerts (Story 21.6 / AD-41)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    Lead,
    Permission,
    ZaloConnection,
    ZaloMessageLog,
    get_async_session,
)
from app.gateway.zalo.client import (
    ZaloClient,
    format_vietnam_phone,
    generate_assisted_outbound_draft,
)
from app.gateway.zalo.telegram_alerts import send_telegram_lead_alert
from app.gateway.zalo.webhook import (
    handle_zalo_webhook_event,
    verify_zalo_signature,
)
from app.users import get_auth_context
from app.utils.oauth_security import TokenEncryption
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(tags=["outbound"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class ZaloDraftRequest(BaseModel):
    custom_context: str | None = Field(
        default=None, description="Optional extra context to append to AI draft"
    )


class ZaloDraftResponse(BaseModel):
    lead_id: UUID
    phone: str
    clean_phone: str
    zalo_url: str
    draft: str
    company_name: str
    log_id: UUID | None = None


class ZnsSendRequest(BaseModel):
    template_id: str = Field(..., description="Approved Zalo OA ZNS Template ID")
    template_data: dict[str, Any] = Field(
        ..., description="Data parameters matching the ZNS template specification"
    )
    tracking_id: str | None = Field(
        default=None, description="Client-side correlation / tracking ID"
    )
    consent_confirmed: bool = Field(
        default=False,
        description="Explicit user consent confirmation complying with Decree 356",
    )
    mode: str | None = Field(
        default=None, description="Optional mode, e.g. 'development' for test templates"
    )


class ZnsSendResponse(BaseModel):
    status: str
    msg_id: str | None = None
    recipient_phone: str
    error: str | None = None
    log_id: UUID | None = None


class ZaloConnectionCreate(BaseModel):
    oa_id: str = Field(..., min_length=1, max_length=100)
    oa_name: str | None = Field(default=None, max_length=255)
    app_id: str | None = Field(default=None, max_length=100)
    access_token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
    webhook_secret: str | None = Field(default=None, max_length=255)
    expires_in_seconds: int = Field(default=90000)


class ZaloConnectionRead(BaseModel):
    id: UUID
    workspace_id: int
    oa_id: str
    oa_name: str | None
    app_id: str | None
    is_active: bool
    token_expires_at: datetime | None
    created_at: datetime


class TelegramAlertRequest(BaseModel):
    message_content: str | None = Field(default=None)
    intent: str | None = Field(default="Tín hiệu quan tâm từ Zalo")
    chat_id: str | None = Field(default=None)


class TelegramAlertResponse(BaseModel):
    sent: bool
    message_id: str | None = None
    chat_id: str | None = None
    text: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _get_lead_or_404(
    session: AsyncSession, lead_id: UUID, workspace_id: int | None = None
) -> Lead:
    stmt = (
        select(Lead)
        .options(selectinload(Lead.verified_contacts))
        .where(Lead.id == lead_id)
    )
    if workspace_id is not None:
        stmt = stmt.where(Lead.workspace_id == workspace_id)

    res = await session.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with id '{lead_id}' not found",
        )
    return lead


def _resolve_lead_phone(lead: Lead) -> str:
    if getattr(lead, "phone", None):
        return str(lead.phone)
    if getattr(lead, "verified_contacts", None):
        for contact in lead.verified_contacts:
            if getattr(contact, "phone_number", None):
                return str(contact.phone_number)
            if getattr(contact, "phone", None):
                return str(contact.phone)
    return ""


# ---------------------------------------------------------------------------
# Assisted Outbound Co-pilot (Deep-link & AI Greeting Script)
# ---------------------------------------------------------------------------


@router.post(
    "/leads/{lead_id}/zalo-draft",
    response_model=ZaloDraftResponse,
    summary="Generate Assisted Zalo Outreach draft script and deep-link (Story 21.6)",
)
@router.post(
    "/workspaces/{workspace_id}/leads/{lead_id}/zalo-draft",
    response_model=ZaloDraftResponse,
    summary="Generate Assisted Zalo Outreach draft script and deep-link (Workspace scoped)",
)
async def generate_zalo_draft(
    lead_id: UUID,
    workspace_id: int | None = None,
    payload: ZaloDraftRequest | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ZaloDraftResponse:
    """Generate personalized Vietnamese outreach message for Assisted Zalo Co-pilot.

    Enforces 100% ToS compliance: Returns deep-link (https://zalo.me/{clean_phone})
    for client opening and copies draft to clipboard.
    """
    lead = await _get_lead_or_404(session, lead_id, workspace_id)
    target_ws = lead.workspace_id

    await check_permission(auth, target_ws, Permission.VIEW_DOCUMENTS, session=session)

    raw_phone = _resolve_lead_phone(lead)
    phone_meta = format_vietnam_phone(raw_phone)
    clean_phone = phone_meta["clean_phone"]
    zalo_url = phone_meta["zalo_url"]

    # Build context dictionary
    lead_dict = {
        "company_name": lead.company_name,
        "source": lead.source,
        "industry": lead.industry,
        "location": lead.location,
        "intent": getattr(lead, "intent", None) or "BÁN",
        "price_estimate": getattr(lead, "price_estimate", None),
        "content_snippet": getattr(lead, "content_snippet", None),
        "author": getattr(lead, "author", None),
    }

    custom_ctx = payload.custom_context if payload else None
    draft_text = generate_assisted_outbound_draft(lead_dict, custom_context=custom_ctx)

    # Log draft generation
    log_entry = ZaloMessageLog(
        workspace_id=target_ws,
        lead_id=lead.id,
        recipient_phone=clean_phone,
        message_type="assisted_draft",
        content=draft_text,
        status="generated",
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)

    return ZaloDraftResponse(
        lead_id=lead.id,
        phone=raw_phone,
        clean_phone=clean_phone,
        zalo_url=zalo_url,
        draft=draft_text,
        company_name=lead.company_name,
        log_id=log_entry.id,
    )


# ---------------------------------------------------------------------------
# ZNS (Zalo Notification Service) Official Sender
# ---------------------------------------------------------------------------


@router.post(
    "/leads/{lead_id}/zns-send",
    response_model=ZnsSendResponse,
    summary="Send transactional ZNS message via Zalo OA OpenAPI (Story 21.6)",
)
@router.post(
    "/workspaces/{workspace_id}/leads/{lead_id}/zns-send",
    response_model=ZnsSendResponse,
    summary="Send transactional ZNS message via Zalo OA OpenAPI (Workspace scoped)",
)
async def send_zns_message(
    lead_id: UUID,
    payload: ZnsSendRequest,
    workspace_id: int | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ZnsSendResponse:
    """Send transactional notification via official Zalo OA ZNS endpoint.

    Requires template_id and compliance with Decree 356 consent.
    """
    lead = await _get_lead_or_404(session, lead_id, workspace_id)
    target_ws = lead.workspace_id

    await check_permission(auth, target_ws, Permission.EDIT_DOCUMENTS, session=session)

    # Decree 356 Consent Verification Guardrail
    has_consent = (
        payload.consent_confirmed
        or lead.consent_status in ("consented", "opted_in")
        or bool(lead.legal_basis)
    )
    if not has_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decree 356 compliance error: ZNS messages require verified user consent or explicit consent confirmation.",
        )

    raw_phone = _resolve_lead_phone(lead)
    phone_meta = format_vietnam_phone(raw_phone)
    int_phone = phone_meta["international_phone"]
    if not int_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead does not have a valid Vietnamese phone number for ZNS delivery.",
        )

    # Fetch active Zalo Connection for workspace
    conn_stmt = select(ZaloConnection).where(
        ZaloConnection.workspace_id == target_ws,
        ZaloConnection.is_active.is_(True),
    )
    conn_res = await session.execute(conn_stmt)
    connection = conn_res.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No active Zalo OA connection found for workspace {target_ws}. Please configure Zalo OA first.",
        )

    client = ZaloClient.from_connection(connection)
    try:
        await client.ensure_valid_token(session, connection)
        result = await client.send_zns(
            phone=int_phone,
            template_id=payload.template_id,
            template_data=payload.template_data,
            tracking_id=payload.tracking_id,
            mode=payload.mode,
        )
    except Exception as exc:
        logger.error("ZNS send failed: %s", exc)
        log_entry = ZaloMessageLog(
            workspace_id=target_ws,
            zalo_connection_id=connection.id,
            lead_id=lead.id,
            recipient_phone=int_phone,
            message_type="zns",
            template_id=payload.template_id,
            template_data=payload.template_data,
            content=f"ZNS Template: {payload.template_id}",
            status="failed",
            error_message=str(exc),
        )
        session.add(log_entry)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Zalo ZNS API error: {exc}",
        ) from exc
    finally:
        await client.close()

    error_code = result.get("error", 0)
    msg_id = (
        result.get("data", {}).get("msg_id")
        if isinstance(result.get("data"), dict)
        else None
    )
    success = error_code == 0

    log_entry = ZaloMessageLog(
        workspace_id=target_ws,
        zalo_connection_id=connection.id,
        lead_id=lead.id,
        recipient_phone=int_phone,
        message_type="zns",
        template_id=payload.template_id,
        template_data=payload.template_data,
        content=f"ZNS Template: {payload.template_id}",
        status="sent" if success else "failed",
        external_message_id=str(msg_id) if msg_id else None,
        error_message=result.get("message") if not success else None,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)

    if not success:
        return ZnsSendResponse(
            status="failed",
            recipient_phone=int_phone,
            error=result.get("message") or f"Zalo error code {error_code}",
            log_id=log_entry.id,
        )

    return ZnsSendResponse(
        status="sent",
        msg_id=str(msg_id) if msg_id else None,
        recipient_phone=int_phone,
        log_id=log_entry.id,
    )


# ---------------------------------------------------------------------------
# Workspace Zalo Connection Management
# ---------------------------------------------------------------------------


@router.get(
    "/workspaces/{workspace_id}/zalo/connection",
    response_model=ZaloConnectionRead | None,
    summary="Get active Zalo OA connection for workspace",
)
async def get_workspace_zalo_connection(
    workspace_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ZaloConnectionRead | None:
    await check_permission(
        auth, workspace_id, Permission.VIEW_DOCUMENTS, session=session
    )

    stmt = select(ZaloConnection).where(
        ZaloConnection.workspace_id == workspace_id,
        ZaloConnection.is_active.is_(True),
    )
    res = await session.execute(stmt)
    conn = res.scalar_one_or_none()
    if not conn:
        return None

    return ZaloConnectionRead(
        id=conn.id,
        workspace_id=conn.workspace_id,
        oa_id=conn.oa_id,
        oa_name=conn.oa_name,
        app_id=conn.app_id,
        is_active=conn.is_active,
        token_expires_at=conn.token_expires_at,
        created_at=conn.created_at,
    )


@router.post(
    "/workspaces/{workspace_id}/zalo/connection",
    response_model=ZaloConnectionRead,
    summary="Create or update Zalo OA connection for workspace",
)
async def upsert_workspace_zalo_connection(
    workspace_id: int,
    payload: ZaloConnectionCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ZaloConnectionRead:
    await check_permission(auth, workspace_id, Permission.ADMIN_USERS, session=session)

    secret = config.SECRET_KEY or ""
    enc = TokenEncryption(secret) if secret else None

    access_enc = (
        enc.encrypt_token(payload.access_token)
        if enc and payload.access_token
        else payload.access_token
    )
    refresh_enc = (
        enc.encrypt_token(payload.refresh_token)
        if enc and payload.refresh_token
        else payload.refresh_token
    )

    expires_at = (
        datetime.now(UTC) + timedelta(seconds=payload.expires_in_seconds)
        if payload.access_token
        else None
    )

    stmt = select(ZaloConnection).where(
        ZaloConnection.workspace_id == workspace_id,
        ZaloConnection.oa_id == payload.oa_id,
    )
    res = await session.execute(stmt)
    conn = res.scalar_one_or_none()

    if conn:
        conn.oa_name = payload.oa_name or conn.oa_name
        conn.app_id = payload.app_id or conn.app_id
        if access_enc:
            conn.access_token_encrypted = access_enc
        if refresh_enc:
            conn.refresh_token_encrypted = refresh_enc
        if expires_at:
            conn.token_expires_at = expires_at
        if payload.webhook_secret:
            conn.webhook_secret = payload.webhook_secret
        conn.is_active = True
    else:
        conn = ZaloConnection(
            workspace_id=workspace_id,
            oa_id=payload.oa_id,
            oa_name=payload.oa_name,
            app_id=payload.app_id,
            access_token_encrypted=access_enc,
            refresh_token_encrypted=refresh_enc,
            token_expires_at=expires_at,
            webhook_secret=payload.webhook_secret,
            is_active=True,
        )
        session.add(conn)

    await session.commit()
    await session.refresh(conn)

    return ZaloConnectionRead(
        id=conn.id,
        workspace_id=conn.workspace_id,
        oa_id=conn.oa_id,
        oa_name=conn.oa_name,
        app_id=conn.app_id,
        is_active=conn.is_active,
        token_expires_at=conn.token_expires_at,
        created_at=conn.created_at,
    )


# ---------------------------------------------------------------------------
# Telegram Lead Alert Dispatcher
# ---------------------------------------------------------------------------


@router.post(
    "/leads/{lead_id}/telegram-alert",
    response_model=TelegramAlertResponse,
    summary="Dispatch rich Telegram alert for lead (Story 21.6)",
)
@router.post(
    "/workspaces/{workspace_id}/leads/{lead_id}/telegram-alert",
    response_model=TelegramAlertResponse,
    summary="Dispatch rich Telegram alert for lead (Workspace scoped)",
)
async def dispatch_lead_telegram_alert(
    lead_id: UUID,
    payload: TelegramAlertRequest | None = None,
    workspace_id: int | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> TelegramAlertResponse:
    lead = await _get_lead_or_404(session, lead_id, workspace_id)
    target_ws = lead.workspace_id

    await check_permission(auth, target_ws, Permission.VIEW_DOCUMENTS, session=session)

    raw_phone = _resolve_lead_phone(lead)
    content = (
        payload.message_content
        if payload and payload.message_content
        else (lead.content_snippet or "")
    )
    intent = (
        payload.intent
        if payload and payload.intent
        else (getattr(lead, "intent", None) or "Tín hiệu mua / hợp tác")
    )
    chat_id = payload.chat_id if payload else None

    result = await send_telegram_lead_alert(
        session=session,
        workspace_id=target_ws,
        lead=lead,
        phone=raw_phone,
        message_content=content,
        intent=intent,
        target_chat_id=chat_id,
    )

    return TelegramAlertResponse(
        sent=bool(result.get("sent")),
        message_id=result.get("message_id"),
        chat_id=result.get("chat_id"),
        text=result.get("text"),
        error=result.get("error") or result.get("reason"),
    )


# ---------------------------------------------------------------------------
# Public Inbound Webhook Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/gateway/zalo/webhook",
    summary="Inbound webhook endpoint for Zalo OA events (Story 21.6)",
)
async def zalo_inbound_webhook(
    request: Request,
    x_zevent_signature: str | None = Header(default=None, alias="X-ZEvent-Signature"),
    mac: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    raw_body = await request.body()
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body"
        ) from exc

    app_id = str(data.get("app_id") or "")
    timestamp = str(data.get("timestamp") or "")
    sig = x_zevent_signature or mac or ""

    secret = getattr(config, "ZALO_APP_SECRET", "") or ""
    if not verify_zalo_signature(app_id, raw_body, timestamp, sig, secret):
        logger.warning("Rejected Zalo webhook with invalid signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Zalo webhook signature",
        )

    return await handle_zalo_webhook_event(session, data)
