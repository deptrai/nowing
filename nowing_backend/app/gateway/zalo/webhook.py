"""Zalo OA Inbound Webhook receiver, signature verifier, and intent detector (Story 21.6 / AD-41)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, VerifiedContact, ZaloConnection, ZaloMessageLog
from app.gateway.zalo.telegram_alerts import send_telegram_lead_alert

logger = logging.getLogger(__name__)

BUYING_INTENT_KEYWORDS = [
    "báo giá",
    "bao giá",
    "bảng giá",
    "giá bao nhiêu",
    "giá cả",
    "giá",
    "chi phí",
    "tư vấn",
    "quan tâm",
    "muốn biết",
    "cần thêm",
    "lịch hẹn",
    "hẹn",
    "gặp",
    "demo",
    "trao đổi",
    "alo",
    "gọi lại",
    "mua",
    "thuê",
    "chốt",
    "đặt cọc",
    "hợp tác",
    "ký hợp đồng",
    "sđt",
    "số điện thoại",
    "phone",
    "zalo",
    "inbox",
    "gửi thông tin",
]

OPT_OUT_KEYWORDS = [
    "hủy",
    "từ chối",
    "stop",
    "không quan tâm",
    "không cần",
    "không muốn",
    "không hẹn",
    "không gặp",
    "không mua",
    "không thuê",
    "không đặt cọc",
    "không hợp tác",
    "không ký",
]


def _is_negated(lower_text: str) -> bool:
    """Heuristic: if the message contains a negation word/pair, do not treat it as buying intent."""
    if not lower_text:
        return False
    # Broad negation word present anywhere — keeps naive detector from firing on "không quan tâm".
    negation_words = ["không", "ko", "k", "từ chối", "hủy", "stop", "cấm"]
    for neg in negation_words:
        if re.search(rf"\b{re.escape(neg)}\b", lower_text):
            return True
    return False


def detect_buying_intent(text: str) -> tuple[bool, str]:
    """Detect if incoming message has positive buying/interest intent in Vietnamese."""
    if not text:
        return False, ""
    lower_text = text.lower()
    if _is_negated(lower_text):
        return False, ""
    for kw in BUYING_INTENT_KEYWORDS:
        if re.search(rf"(?<![\w]){re.escape(kw)}(?![\w])", lower_text):
            return True, f"Khớp từ khóa: '{kw}'"
    return False, ""


def detect_opt_out(text: str) -> bool:
    """Detect explicit opt-out / unsubscribe intent in Vietnamese."""
    if not text:
        return False
    lower_text = text.lower()
    return any(re.search(rf"(?<![\w]){re.escape(kw)}(?![\w])", lower_text) for kw in OPT_OUT_KEYWORDS)


_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


def verify_zalo_signature(
    app_id: str,
    raw_body: bytes,
    timestamp: str,
    signature: str,
    secret_key: str,
) -> bool:
    """Verify Zalo OA webhook signature.

    Supports the official Zalo webhook MAC:
        sha256(app_id + raw_body_utf8 + timestamp + secret_key)
    And an HMAC-SHA256(raw_body, secret_key) fallback used by some integrations.
    Rejects missing secrets, missing signatures, and stale/missing timestamps.
    """
    if not secret_key:
        logger.warning("Zalo webhook secret is not configured; failing closed.")
        return False
    if not signature:
        return False
    if not timestamp:
        return False

    # Timestamp replay / drift guard
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    import time

    now = int(time.time())
    if abs(now - ts) > _WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
        logger.warning("Zalo webhook timestamp outside tolerance: %s", timestamp)
        return False

    body_str = raw_body.decode("utf-8", errors="ignore")

    # 1. Standard Zalo OA MAC hash: sha256(app_id + body + timestamp + secret)
    data_to_hash = f"{app_id}{body_str}{timestamp}{secret_key}".encode()
    expected_mac = hashlib.sha256(data_to_hash).hexdigest()
    if hmac.compare_digest(signature.lower(), expected_mac.lower()):
        return True

    # 2. HMAC-SHA256 of raw body with secret_key
    hmac_digest = hmac.new(secret_key.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.lower(), hmac_digest.lower())


async def _find_lead_for_inbound(
    session: AsyncSession,
    workspace_id: int,
    sender_id: str,
    sender_phone: str | None,
) -> Lead | None:
    """Match a lead deterministically by phone or zalo user id.

    Falls back to the sender phone (if present) mapped through VerifiedContact.
    Never matches company_name against a Zalo user id.
    """
    if not sender_id and not sender_phone:
        return None

    if sender_phone:
        stmt = (
            select(Lead)
            .join(VerifiedContact, VerifiedContact.lead_id == Lead.id)
            .where(
                Lead.workspace_id == workspace_id,
                VerifiedContact.phone == sender_phone,
            )
            .limit(1)
        )
        res = await session.execute(stmt)
        lead = res.scalar_one_or_none()
        if lead:
            return lead

    if sender_id and hasattr(Lead, "zalo_user_id"):
            stmt = (
                select(Lead)
                .where(
                    Lead.workspace_id == workspace_id,
                    Lead.zalo_user_id == sender_id,
                )
                .limit(1)
            )
            res = await session.execute(stmt)
            return res.scalar_one_or_none() or None

    return None


async def handle_zalo_webhook_event(
    session: AsyncSession,
    connection: ZaloConnection,
    event_data: dict[str, Any],
) -> dict[str, Any]:
    """Process inbound Zalo webhook event, log message, and dispatch Telegram alerts on high intent."""
    if not isinstance(event_data, dict):
        raise TypeError("event_data must be a dict")

    event_name = str(event_data.get("event_name") or event_data.get("event") or "unknown")
    workspace_id = connection.workspace_id

    logger.info("Handling Zalo webhook event=%s, oa_id=%s", event_name, connection.oa_id)

    # 1. Parse message payload
    sender = event_data.get("sender") or {}
    sender_id = str(sender.get("id") or "")
    sender_phone = str(sender.get("phone") or "") or None
    message = event_data.get("message") or {}
    text_content = str(message.get("text") or event_data.get("text") or "").strip()
    msg_id = str(message.get("msg_id") or event_data.get("msg_id") or "")

    # 2. Idempotency check
    if msg_id and connection.id:
        existing = await session.execute(
            select(ZaloMessageLog).where(
                ZaloMessageLog.zalo_connection_id == connection.id,
                ZaloMessageLog.external_message_id == msg_id,
            )
        )
        if existing.scalar_one_or_none():
            return {
                "status": "ok",
                "event": event_name,
                "log_id": None,
                "has_intent": False,
                "telegram_alert": None,
                "duplicate": True,
            }

    # 3. Find matching Lead if any
    lead = await _find_lead_for_inbound(session, workspace_id, sender_id, sender_phone)

    # 4. Opt-out detection
    if detect_opt_out(text_content) and lead:
        lead.consent_status = "opted_out"
        lead.legal_basis = None

    # 5. Log inbound message (redact raw event body; content is already extracted)
    log_entry = ZaloMessageLog(
        workspace_id=workspace_id,
        zalo_connection_id=connection.id,
        lead_id=lead.id if lead else None,
        recipient_phone=sender_phone,
        recipient_zalo_id=sender_id,
        message_type="webhook_inbound",
        content=text_content or f"Event: {event_name}",
        status="received",
        external_message_id=msg_id,
        template_data={},
    )
    session.add(log_entry)

    # 6. Check intent and trigger Telegram alert only on buying intent
    has_intent, intent_reason = detect_buying_intent(text_content)
    telegram_result = None

    if has_intent:
        telegram_result = await send_telegram_lead_alert(
            session=session,
            workspace_id=workspace_id,
            lead=lead,
            phone=lead.phone if lead else None,
            message_content=text_content,
            intent=intent_reason,
        )

    await session.commit()
    await session.refresh(log_entry)

    return {
        "status": "ok",
        "event": event_name,
        "log_id": str(log_entry.id),
        "has_intent": has_intent,
        "telegram_alert": telegram_result,
    }
