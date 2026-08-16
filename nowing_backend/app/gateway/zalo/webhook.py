"""Zalo Official Account Webhook Handler & Signature Verification.

Processes inbound messages, status callbacks, opt-out requests,
and buying-intent signals from Zalo OA Webhooks.
Adheres to Decree 91/2020/ND-CP on anti-spam consent management.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, VerifiedContact, ZaloConnection, ZaloMessageLog

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Decree 91/2020/ND-CP Art. 12: Mandatory processing of unsubscribe requests
OPT_OUT_KEYWORDS = {
    "tc",
    "tu choi",
    "từ chối",
    "stop",
    "ngung",
    "ngừng",
    "huy",
    "hủy",
    "unsubscribe",
    "dung gui",
    "đừng gửi",
    "khong nhan",
    "không nhận",
    "cut",
    "cút",
    "lam phien",
    "làm phiền",
}

# Buying intent triggers for sales alerts
BUYING_INTENT_KEYWORDS = {
    "gia",
    "giá",
    "bao nhieu",
    "bao nhiêu",
    "bang gia",
    "bảng giá",
    "gui thong tin",
    "gửi thông tin",
    "tu van",
    "tư vấn",
    "xem nha",
    "xem nhà",
    "dat coc",
    "đặt cọc",
    "con hang",
    "còn hàng",
    "chiet khau",
    "chiết khấu",
    "so do",
    "sổ đỏ",
    "phap ly",
    "pháp lý",
    "mat bang",
    "mặt bằng",
    "can ho",
    "căn hộ",
    "biet thu",
    "biệt thự",
    "nha pho",
    "nhà phố",
    "shophouse",
}

# Maximum timestamp tolerance for webhook replay attacks (seconds)
_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


def detect_buying_intent(text: str) -> tuple[bool, str | None]:
    """Detect if an inbound Zalo message expresses purchasing/inquiry intent."""
    if not text:
        return False, None
    lower_text = text.lower()
    for kw in BUYING_INTENT_KEYWORDS:
        if re.search(rf"(?<![\w]){re.escape(kw)}(?![\w])", lower_text):
            return True, kw
    return False, None


def detect_opt_out(text: str) -> bool:
    """Detect explicit opt-out / unsubscribe intent in Vietnamese."""
    if not text:
        return False
    lower_text = text.lower()
    return any(
        re.search(rf"(?<![\w]){re.escape(kw)}(?![\w])", lower_text)
        for kw in OPT_OUT_KEYWORDS
    )


def check_timestamp_freshness(
    timestamp: int | str, max_drift_seconds: int = 300
) -> bool:
    """Check that incoming webhook timestamp is within tolerance (anti-replay guard)."""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False

    # Handle milliseconds if provided
    if ts > 100_000_000_000:
        ts = int(ts / 1000)

    now = int(time.time())
    if abs(now - ts) > max_drift_seconds:
        logger.warning(
            "Zalo webhook timestamp %s outside freshness tolerance of %ss (drift=%ss)",
            timestamp,
            max_drift_seconds,
            abs(now - ts),
        )
        return False
    return True


def verify_zalo_signature(
    app_id: str | None = None,
    raw_body: bytes = b"",
    timestamp: str | int | None = None,
    signature: str = "",
    secret_key: str | None = None,
    *,
    secret: str | None = None,
) -> bool:
    """Verify Zalo OA webhook signature with strict anti-replay and prefix stripping."""
    effective_secret = secret or secret_key
    if not effective_secret:
        logger.warning("Zalo webhook secret is not configured; failing closed.")
        return False
    if not signature:
        return False

    clean_sig = signature.lower().removeprefix("mac=").removeprefix("sha256=").strip()

    # Check timestamp freshness if supplied
    if timestamp is not None and not check_timestamp_freshness(
        timestamp, _WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS
    ):
        return False

    # Check 1: Direct HMAC-SHA256 of raw body
    hmac_digest = hmac.new(
        effective_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(clean_sig, hmac_digest.lower()):
        return True

    # Check 2: Standard Zalo OA MAC hash: sha256(app_id + body + timestamp + secret)
    if app_id and timestamp is not None:
        body_str = raw_body.decode("utf-8", errors="ignore")
        data_to_hash = f"{app_id}{body_str}{timestamp}{effective_secret}".encode()
        expected_mac = hashlib.sha256(data_to_hash).hexdigest()
        if hmac.compare_digest(clean_sig, expected_mac.lower()):
            return True

    return False


async def _find_lead_for_inbound(
    session: AsyncSession,
    workspace_id: int,
    sender_id: str,
    sender_phone: str | None,
) -> Lead | None:
    """Match a lead deterministically by phone or zalo user id."""
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
    connection: ZaloConnection | None,
    event_data: dict[str, Any],
    workspace_id: int | None = None,
) -> dict[str, Any]:
    """Process inbound Zalo webhook event, log message, and dispatch Telegram alerts on high intent (AC-1, AC-3)."""
    if not isinstance(event_data, dict):
        raise TypeError("event_data must be a dict")

    event_name = str(
        event_data.get("event_name") or event_data.get("event") or "unknown"
    )
    ws_id = workspace_id or (connection.workspace_id if connection else 1)
    conn_id = connection.id if connection else None

    logger.info("Handling Zalo webhook event=%s, ws_id=%s", event_name, ws_id)

    # 1. Parse message payload
    sender = event_data.get("sender") or {}
    sender_id = str(sender.get("id") or "")
    sender_phone = str(sender.get("phone") or "") or None
    message = event_data.get("message") or {}
    text_content = str(message.get("text") or event_data.get("text") or "").strip()
    msg_id = str(message.get("msg_id") or event_data.get("msg_id") or "")

    # 2. Idempotency check across workspace
    if msg_id:
        existing = await session.execute(
            select(ZaloMessageLog).where(
                ZaloMessageLog.workspace_id == ws_id,
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
    lead = await _find_lead_for_inbound(session, ws_id, sender_id, sender_phone)

    # 4. Event-specific handling & Lead status transitions (AC-3)
    if event_name in ("user_send_text", "user_send_image"):
        if lead:
            lead.status = "responded"
        if detect_opt_out(text_content) and lead:
            lead.consent_status = "opted_out"
            lead.legal_basis = None
    elif event_name == "unfollow":
        if lead:
            lead.consent_status = "opted_out"
    elif event_name == "follow":
        if lead and lead.status == "new":
            lead.status = "contacted"

    # 5. Log inbound message
    log_entry = ZaloMessageLog(
        workspace_id=ws_id,
        zalo_connection_id=conn_id,
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

    # Commit DB transaction first
    await session.commit()
    await session.refresh(log_entry)

    # 6. Check intent and trigger Telegram alert safely after commit
    has_intent, intent_reason = detect_buying_intent(text_content)
    telegram_result = None

    if has_intent:
        try:
            from app.gateway.zalo.client import send_telegram_lead_alert

            telegram_result = await send_telegram_lead_alert(
                session=session,
                workspace_id=ws_id,
                lead=lead,
                phone=lead.phone if lead else None,
                message_content=text_content,
                intent=intent_reason,
            )
        except Exception as alert_err:
            logger.error("Failed to dispatch Telegram lead alert: %s", alert_err)

    return {
        "status": "ok",
        "event": event_name,
        "log_id": str(log_entry.id),
        "has_intent": has_intent,
        "telegram_alert": telegram_result,
    }
