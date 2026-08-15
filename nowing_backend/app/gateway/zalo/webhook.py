"""Zalo OA Inbound Webhook receiver, signature verifier, and intent detector (Story 21.6 / AD-41)."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, ZaloConnection, ZaloMessageLog
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


def verify_zalo_signature(
    app_id: str,
    raw_body: bytes,
    timestamp: str,
    signature: str,
    secret_key: str,
) -> bool:
    """Verify Zalo OA webhook signature (X-ZEvent-Signature or mac).

    Formula: sha256(app_id + raw_body_utf8 + timestamp + secret_key)
    Or HMAC-SHA256(raw_body, secret_key)
    """
    if not secret_key:
        return True  # Dev / test environment bypass if no secret configured

    if not signature:
        return False

    # 1. Try standard Zalo OA MAC hash: sha256(app_id + body + timestamp + secret)
    body_str = raw_body.decode("utf-8", errors="ignore")
    data_to_hash = f"{app_id}{body_str}{timestamp}{secret_key}".encode()
    expected_mac = hashlib.sha256(data_to_hash).hexdigest()

    if hmac.compare_digest(signature.lower(), expected_mac.lower()):
        return True

    # 2. Try HMAC-SHA256 of body with secret_key
    hmac_digest = hmac.new(secret_key.encode(), raw_body, hashlib.sha256).hexdigest()
    if hmac.compare_digest(signature.lower(), hmac_digest.lower()):
        return True

    # 3. Try sha256(secret_key + timestamp + body)
    alt_hash = hashlib.sha256(f"{secret_key}{timestamp}{body_str}".encode()).hexdigest()
    return hmac.compare_digest(signature.lower(), alt_hash.lower())


def detect_buying_intent(text: str) -> tuple[bool, str]:
    """Detect if incoming message has positive buying/interest intent in Vietnamese."""
    if not text:
        return False, ""
    lower_text = text.lower()
    for kw in BUYING_INTENT_KEYWORDS:
        if kw in lower_text:
            return True, f"Khớp từ khóa: '{kw}'"
    return False, ""


async def handle_zalo_webhook_event(
    session: AsyncSession,
    event_data: dict[str, Any],
) -> dict[str, Any]:
    """Process inbound Zalo webhook event, log message, and dispatch Telegram alerts on high intent."""
    event_name = event_data.get("event_name") or event_data.get("event") or "unknown"
    oa_id = str(
        event_data.get("oa_id") or event_data.get("recipient", {}).get("id") or ""
    )
    app_id = str(event_data.get("app_id") or "")

    logger.info("Handling Zalo webhook event=%s, oa_id=%s", event_name, oa_id)

    # 1. Resolve ZaloConnection
    connection_stmt = select(ZaloConnection).where(ZaloConnection.is_active.is_(True))
    if oa_id:
        connection_stmt = connection_stmt.where(ZaloConnection.oa_id == oa_id)
    elif app_id:
        connection_stmt = connection_stmt.where(ZaloConnection.app_id == app_id)

    res = await session.execute(connection_stmt)
    connection = res.scalar_one_or_none()

    workspace_id = connection.workspace_id if connection else 1

    # 2. Parse message payload
    sender = event_data.get("sender") or {}
    sender_id = str(sender.get("id") or "")
    message = event_data.get("message") or {}
    text_content = str(message.get("text") or event_data.get("text") or "").strip()
    msg_id = str(message.get("msg_id") or event_data.get("msg_id") or "")

    # 3. Find matching Lead if any
    lead = None
    if sender_id:
        lead_stmt = (
            select(Lead)
            .where(
                Lead.workspace_id == workspace_id,
                Lead.company_name.ilike(f"%{sender_id}%"),
            )
            .limit(1)
        )
        lead_res = await session.execute(lead_stmt)
        lead = lead_res.scalar_one_or_none()

    # 4. Log inbound message
    recipient_phone = sender_id if sender_id and sender_id.isdigit() else None
    log_entry = ZaloMessageLog(
        workspace_id=workspace_id,
        zalo_connection_id=connection.id if connection else None,
        lead_id=lead.id if lead else None,
        recipient_phone=recipient_phone,
        recipient_zalo_id=sender_id,
        message_type="webhook_inbound",
        content=text_content or f"Event: {event_name}",
        status="received",
        external_message_id=msg_id,
        template_data=event_data,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)

    # 5. Check intent and trigger Telegram alert if buying signal is detected
    has_intent, intent_reason = detect_buying_intent(text_content)
    telegram_result = None

    if has_intent or event_name == "user_send_text":
        alert_intent = intent_reason if has_intent else "Phản hồi tin nhắn Zalo"
        telegram_result = await send_telegram_lead_alert(
            session=session,
            workspace_id=workspace_id,
            lead=lead,
            phone=lead.phone if lead else sender_id,
            message_content=text_content,
            intent=alert_intent,
        )

    return {
        "status": "ok",
        "event": event_name,
        "log_id": str(log_entry.id),
        "has_intent": has_intent,
        "telegram_alert": telegram_result,
    }
