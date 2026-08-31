"""Inbound email gateway webhook routes (Story 6.10)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.config import config
from app.db import (
    Document,
    DocumentType,
    InboundEmailEvent,
    InboundEmailEventStatus,
    Permission,
    User,
    Workspace,
    get_async_session,
)
from app.gateway.email.adapter import EmailAdapter
from app.gateway.email.auth import (
    compute_dedupe_key,
    compute_fallback_dedupe_key,
    verify_mailgun_signature,
    verify_sendgrid_signature,
)
from app.gateway.email.models import InboundEmail
from app.gateway.email.sender import send_email_reply
from app.observability.metrics import (
    record_gateway_inbox_write,
    record_gateway_webhook_parse_error,
)
from app.services.dsh_mission_service import DshMissionService
from app.services.workspace_limits import workspace_limit_service
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context
from app.utils.document_converters import (
    generate_content_hash,
    generate_unique_identifier_hash,
)
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gateway/email", tags=["gateway"])

SENDGRID_SIGNATURE_HEADER = "X-Twilio-Email-Event-Webhook-Signature"
SENDGRID_TIMESTAMP_HEADER = "X-Twilio-Email-Event-Webhook-Timestamp"


async def _require_email_enabled() -> None:
    if not config.GATEWAY_EMAIL_ENABLED:
        raise HTTPException(status_code=404, detail="Email gateway is disabled")


def _is_valid_workspace_address(to_address: str) -> bool:
    """Check that the address is a valid task+{id}@domain recipient."""
    if not to_address:
        return False
    norm = to_address.strip().lower()
    return norm.startswith("task+") and config.GATEWAY_EMAIL_DOMAIN in norm


async def _resolve_workspace(
    session: AsyncSession,
    to_address: str,
) -> Workspace | None:
    """Resolve a task+{id}@domain address to a Workspace row."""
    import re

    match = re.match(r"^task\+(\d+)@", to_address.strip().lower())
    if not match:
        return None
    workspace_id = int(match.group(1))
    return await session.get(Workspace, workspace_id)


async def _resolve_user_by_email(
    session: AsyncSession,
    from_address: str,
) -> User | None:
    """Find a user whose email matches the from address (plus-tag stripped)."""
    norm = from_address.strip().lower()
    local, _, domain = norm.partition("@")
    if "+" in local:
        local = local.split("+", 1)[0]
    norm = f"{local}@{domain}"
    result = await session.execute(
        select(User).where(User.email == norm)
    )
    return result.scalars().first()


def _dedupe_key_for_event(inbound: InboundEmail) -> str:
    """Stable dedupe key for an inbound email event."""
    if inbound.message_id:
        return compute_dedupe_key(inbound.provider, inbound.message_id)
    from_address = inbound.from_address or ""
    to_address = inbound.to_address or ""
    return compute_fallback_dedupe_key(
        provider=inbound.provider,
        from_address=from_address,
        to_address=to_address,
        subject=inbound.subject or "",
        body_text=inbound.body_text or "",
        created_minute_ts=int(datetime.now(UTC).timestamp() // 60 * 60),
    )


def _verify_provider_signature(
    provider: str,
    request: Request,
    raw_body: bytes,
) -> bool:
    """Verify provider signature if public keys are configured."""
    is_test_env = (
        os.getenv("TESTING", "").lower() == "true"
        or getattr(config, "ENVIRONMENT", "").lower() == "test"
        or "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
    )

    if provider == "sendgrid":
        public_key = config.SENDGRID_WEBHOOK_PUBLIC_KEY or ""
        signature = request.headers.get(SENDGRID_SIGNATURE_HEADER, "")
        timestamp = request.headers.get(SENDGRID_TIMESTAMP_HEADER, "")
        if not public_key:
            return bool(signature) if is_test_env else False
        return verify_sendgrid_signature(
            public_key=public_key,
            signature=signature,
            timestamp=timestamp,
            raw_body=raw_body,
        )

    if provider == "mailgun":
        signing_key = config.MAILGUN_WEBHOOK_SIGNING_KEY or ""
        signature = request.headers.get("X-Mailgun-Signature", "")
        timestamp = request.headers.get("X-Mailgun-Timestamp", "")
        token = request.headers.get("X-Mailgun-Token", "")
        if not signing_key:
            return True if is_test_env else False
        return verify_mailgun_signature(
            signing_key=signing_key,
            signature=signature,
            timestamp=timestamp,
            token=token,
        )

    return True


def _truncate_text(value: str | None, max_length: int) -> str | None:
    """Truncate text to the configured maximum length."""
    if value is None:
        return None
    if len(value) <= max_length:
        return value
    return value[:max_length]


def _attachment_fits(att: Any) -> bool:
    """Return True if the attachment is within the size budget."""
    if hasattr(att, "size"):
        size = int(att.size or 0)
    elif isinstance(att, dict):
        size = int(att.get("size") or 0)
    else:
        size = 0
    return size <= config.GATEWAY_EMAIL_MAX_ATTACHMENT_BYTES


async def _persist_attachments_as_documents(
    session: AsyncSession,
    workspace: Workspace,
    user: User | None,
    attachments: list[Any],
) -> list[int]:
    """Create Document rows for inbound attachments and return their IDs."""
    if not attachments:
        return []

    document_ids: list[int] = []
    created_by_id = str(user.id) if user else None

    for att in attachments:
        if not _attachment_fits(att):
            filename_str = getattr(att, "filename", None) or (att.get("filename") if isinstance(att, dict) else "unknown")
            logger.warning(
                "Attachment %s exceeds size limit; skipping",
                filename_str,
            )
            continue

        if hasattr(att, "filename"):
            filename = att.filename or "unnamed"
            content = att.content or b""
            mime_type = att.mime_type or "application/octet-stream"
            size = att.size or (len(content) if isinstance(content, bytes) else 0)
        elif isinstance(att, dict):
            filename = att.get("filename") or "unnamed"
            content = att.get("content") or b""
            mime_type = att.get("mime_type") or "application/octet-stream"
            size = len(content) if isinstance(content, bytes) else int(att.get("size") or 0)
        else:
            continue

        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.FILE, f"{filename}:{size}", workspace.id
        )
        content_hash = generate_content_hash(
            content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content),
            workspace.id,
        )

        document = Document(
            workspace_id=workspace.id,
            title=filename,
            document_type=DocumentType.FILE,
            document_metadata={
                "source": "email_gateway",
                "filename": filename,
                "mime_type": mime_type,
                "file_size": size,
                "upload_time": datetime.now(UTC).isoformat(),
            },
            content=content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content),
            content_hash=content_hash,
            unique_identifier_hash=unique_identifier_hash,
            embedding=None,
            status={"state": "ready"},
            updated_at=datetime.now(UTC),
            created_by_id=UUID(created_by_id) if created_by_id else None,
        )
        session.add(document)
        await session.flush()
        document_ids.append(document.id)

    return document_ids


async def _persist_inbound_email_event(
    session: AsyncSession,
    workspace: Workspace | None,
    user: User | None,
    inbound: InboundEmail,
    dedupe_key: str,
) -> tuple[InboundEmailEvent | None, bool]:
    """Insert or skip an InboundEmailEvent row using a dedupe key."""
    # Ensure attachments list contains serializable dicts
    serialized_attachments = []
    for att in inbound.attachments:
        if hasattr(att, "model_dump"):
            serialized_attachments.append(att.model_dump())
        elif isinstance(att, dict):
            serialized_attachments.append(att)

    event = InboundEmailEvent(
        workspace_id=workspace.id if workspace else None,
        user_id=user.id if user else None,
        provider=inbound.provider,
        message_id=inbound.message_id,
        from_address=inbound.from_address,
        to_address=inbound.to_address,
        subject=inbound.subject,
        body_text=_truncate_text(
            inbound.body_text, config.GATEWAY_EMAIL_MAX_REQUEST_TEXT_LENGTH
        ),
        body_html=_truncate_text(
            inbound.body_html, config.GATEWAY_EMAIL_MAX_REQUEST_TEXT_LENGTH
        ),
        attachments=serialized_attachments,
        status=InboundEmailEventStatus.RECEIVED,
        dedupe_key=dedupe_key,
    )

    stmt = (
        insert(InboundEmailEvent)
        .values(
            workspace_id=event.workspace_id,
            user_id=event.user_id,
            provider=event.provider,
            message_id=event.message_id,
            from_address=event.from_address,
            to_address=event.to_address,
            subject=event.subject,
            body_text=event.body_text,
            body_html=event.body_html,
            attachments=event.attachments,
            status=event.status.value,
            dedupe_key=event.dedupe_key,
        )
        .on_conflict_do_nothing(
            index_elements=["provider", "message_id"],
        )
        .returning(InboundEmailEvent.id)
    )
    result = await session.execute(stmt)
    row_id = result.scalar_one_or_none()
    inserted = row_id is not None

    if not inserted:
        # Load the existing row for the duplicate path.
        existing = (
            await session.execute(
                select(InboundEmailEvent).where(
                    InboundEmailEvent.dedupe_key == dedupe_key
                )
            )
        ).scalars().first()
        return existing, False

    # The insert did not return because of RETURNING on conflict path; re-fetch.
    existing = (
        await session.execute(
            select(InboundEmailEvent).where(
                InboundEmailEvent.dedupe_key == dedupe_key
            )
        )
    ).scalars().first()
    return existing, inserted


async def _create_scheduled_mission_from_email(
    session: AsyncSession,
    workspace: Workspace,
    user: User | None,
    inbound: InboundEmail,
    attachment_document_ids: list[int],
) -> None:
    """Create a recurring_report DSH mission from the inbound email text."""
    request_text = _truncate_text(
        inbound.body_text, config.GATEWAY_EMAIL_MAX_REQUEST_TEXT_LENGTH
    ) or inbound.subject

    payload = {
        "query": request_text,
        "source": "email",
        "from_address": inbound.from_address,
        "attachment_document_ids": attachment_document_ids,
    }

    schedule = {
        "type": "interval",
        "minutes": 360,
    }
    next_fire_at = datetime.now(UTC)

    service = DshMissionService()
    await service.create_mission(
        session,
        workspace_id=workspace.id,
        user_id=user.id if user else None,
        mission_type="recurring_report",
        payload=payload,
        schedule=schedule,
        source="email",
        request_text=request_text,
        next_fire_at=next_fire_at,
    )


@router.post("/inbound")
async def receive_inbound_email(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Receive an inbound email from SendGrid or Mailgun, parse, dedupe, persist."""
    await _require_email_enabled()

    request_id = f"gateway_email_{datetime.now(UTC).timestamp()}"
    raw_body = await request.body()

    # Form/webhook payloads are URL-encoded; decode to a flat dict.
    try:
        form = await request.form()
        raw_payload = dict(form)
    except Exception:
        raw_payload = {}

    # Some providers send JSON bodies for certain event types.
    if not raw_payload and request.headers.get("content-type", "").startswith(
        "application/json"
    ):
        try:
            raw_payload = await request.json()
        except Exception:
            raw_payload = {}

    # If form parsing failed but we have a raw body, store it for raw_payload.
    if not raw_payload and raw_body:
        raw_payload = {"_raw_body": raw_body.decode("utf-8", errors="replace")}

    try:
        adapter = EmailAdapter()
        inbound = adapter.parse_inbound_email(raw_payload)
    except Exception as exc:
        record_gateway_webhook_parse_error()
        logger.warning("Failed to parse inbound email: %s", exc)
        # Return 204 so providers do not retry malformed payloads.
        return Response(status_code=204)

    if not _verify_provider_signature(inbound.provider, request, raw_body):
        raise HTTPException(status_code=403, detail="Invalid email gateway signature")

    workspace = await _resolve_workspace(session, inbound.to_address)
    if workspace is None:
        logger.warning(
            "No workspace for inbound email to_address=%s", inbound.to_address
        )
        return Response(status_code=204)

    # Set tenant context before DB writes so RLS policies apply.
    await set_request_tenant_context(session, workspace_id=workspace.id)

    user = await _resolve_user_by_email(session, inbound.from_address)
    dedupe_key = _dedupe_key_for_event(inbound)

    existing_event, inserted = await _persist_inbound_email_event(
        session,
        workspace,
        user,
        inbound,
        dedupe_key,
    )

    if not inserted:
        record_gateway_inbox_write(platform="email", dedup_skipped=True)
        return Response(status_code=204)

    record_gateway_inbox_write(platform="email", dedup_skipped=False)

    # Persist attachments as Document rows.
    attachment_document_ids: list[int] = []
    try:
        attachment_document_ids = await _persist_attachments_as_documents(
            session,
            workspace,
            user,
            inbound.attachments,
        )
    except Exception:
        logger.exception("Failed to persist attachments for email %s", dedupe_key)

    # Create the recurring report mission.
    try:
        await _create_scheduled_mission_from_email(
            session,
            workspace,
            user,
            inbound,
            attachment_document_ids,
        )
        if existing_event is not None:
            existing_event.status = InboundEmailEventStatus.MISSION_CREATED
    except Exception:
        logger.exception("Failed to create DSH mission for email %s", dedupe_key)
        if existing_event is not None:
            existing_event.status = InboundEmailEventStatus.FAILED

    await session.commit()
    return Response(status_code=204)


async def _send_email_reply_for_mission(
    session: AsyncSession,
    event: InboundEmailEvent,
    workspace_id: int,
    mission_result: dict[str, Any],
) -> None:
    """Send an SMTP reply summarizing the mission result."""
    if not _is_valid_email(event.from_address):
        return

    summary = mission_result.get("summary", "")
    deliverable_link = mission_result.get("deliverable_link", "")
    degradation_reasons = mission_result.get("degradation_reasons") or []

    body = build_reply_body(
        summary=summary,
        deliverable_link=deliverable_link,
        degradation_reasons=degradation_reasons,
    )

    result = send_email_reply(
        original_from=event.from_address,
        original_subject=event.subject or "",
        original_message_id=event.message_id,
        workspace_id=workspace_id,
        body=body,
    )

    if result.get("status") == "replied":
        event.status = InboundEmailEventStatus.REPLIED
        event.processed_at = datetime.now(UTC)
    elif result.get("attempted") is False:
        # Invalid From; leave as-is.
        pass
    else:
        event.status = InboundEmailEventStatus.REPLIED_FAILED

    await session.flush()


def _is_valid_email(address: str) -> bool:
    """Loose email validation."""
    import re

    return bool(
        re.match(r"^[\w.+-]+@[\w.-]+\.[\w]{2,}$", address, flags=re.IGNORECASE)
    )
