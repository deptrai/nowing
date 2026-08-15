"""Telegram rich alert sender for Zalo replies & high-intent leads (Story 21.6 / AD-41)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatPlatform,
    Lead,
)
from app.gateway.accounts import account_token
from app.gateway.telegram.client import TelegramClient
from app.gateway.telegram.formatting import escape_markdown_v2
from app.gateway.zalo.client import format_vietnam_phone

logger = logging.getLogger(__name__)


def build_lead_telegram_alert(
    *,
    lead_name: str,
    company_name: str,
    phone: str,
    source: str,
    intent: str,
    message_content: str,
    workspace_id: int,
    lead_id: str | None = None,
    frontend_url: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build MarkdownV2 text and inline keyboard markup for Telegram lead alert."""
    esc_lead = escape_markdown_v2(lead_name or "Khách hàng")
    esc_company = escape_markdown_v2(company_name or "N/A")
    esc_phone = escape_markdown_v2(phone or "N/A")
    esc_source = escape_markdown_v2(source or "Zalo Outbound")
    esc_intent = escape_markdown_v2(intent or "Tín hiệu mua / hợp tác")
    esc_msg = escape_markdown_v2(
        message_content[:300]
        if message_content
        else "Có phản hồi tích cực từ khách hàng."
    )

    text = (
        "🔥 *TÍN HIỆU LEAD MỚI / PHẢN HỒI ZALO*\n\n"
        f"👤 *Người liên hệ:* {esc_lead}\n"
        f"🏢 *Doanh nghiệp:* {esc_company}\n"
        f"📞 *Số điện thoại:* {esc_phone}\n"
        f"🏷️ *Nguồn:* {esc_source}\n"
        f"🎯 *Tín hiệu:* {esc_intent}\n"
        f'💬 *Nội dung:* "{esc_msg}"'
    )

    phone_meta = format_vietnam_phone(phone)
    zalo_url = phone_meta["zalo_url"] or "https://zalo.me"
    base_fe = (frontend_url or config.NEXT_FRONTEND_URL or "https://nowing.net").rstrip(
        "/"
    )
    lead_url = f"{base_fe}/dashboard/{workspace_id}/leads"
    if lead_id:
        lead_url += f"?search={lead_id}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📱 Mở Zalo", "url": zalo_url},
                {"text": "📋 Xem Chi Tiết Lead", "url": lead_url},
            ]
        ]
    }

    return text, keyboard


async def _resolve_telegram_chat_and_token(
    session: AsyncSession,
    workspace_id: int,
    target_chat_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Resolve a Telegram chat_id and bot token for the workspace.

    If target_chat_id is provided, it must match an active bound ExternalChatBinding
    in the workspace (workspace ownership validation). Otherwise the first active
    bound Telegram binding for the workspace is used.
    """
    stmt = (
        select(ExternalChatBinding, ExternalChatAccount)
        .join(
            ExternalChatAccount,
            ExternalChatBinding.account_id == ExternalChatAccount.id,
        )
        .where(
            ExternalChatBinding.workspace_id == workspace_id,
            ExternalChatBinding.state == ExternalChatBindingState.BOUND,
            ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
        )
        .limit(1)
    )

    if target_chat_id:
        stmt = stmt.where(ExternalChatBinding.external_thread_id == target_chat_id)

    res = await session.execute(stmt)
    row = res.first()
    if row:
        binding, account = row
        chat_id = binding.external_thread_id or binding.external_peer_id
        acc_token = account_token(account)
        return chat_id, (acc_token or config.TELEGRAM_SHARED_BOT_TOKEN or None)

    if target_chat_id:
        logger.warning(
            "Telegram alert skipped: chat_id %s is not a bound workspace chat for workspace %s",
            target_chat_id,
            workspace_id,
        )
        return None, None

    return None, None


async def send_telegram_lead_alert(
    session: AsyncSession,
    *,
    workspace_id: int,
    lead: Lead | None = None,
    phone: str | None = None,
    message_content: str = "",
    intent: str = "Tín hiệu tích cực",
    target_chat_id: str | None = None,
) -> dict[str, Any]:
    """Send rich Telegram alert with Zalo deep-link and Lead details."""
    clean_phone = phone or (lead.phone if lead else "") or ""
    lead_id_str = str(lead.id) if lead else None
    company_name = lead.company_name if lead else "Khách hàng tiềm năng"
    source = lead.source if lead else "Zalo Inbound"
    lead_name = getattr(lead, "author", None) or company_name

    text, reply_markup = build_lead_telegram_alert(
        lead_name=lead_name,
        company_name=company_name,
        phone=clean_phone,
        source=source,
        intent=intent,
        message_content=message_content,
        workspace_id=workspace_id,
        lead_id=lead_id_str,
    )

    # 1. Resolve chat_id and token with workspace ownership validation
    chat_id, token = await _resolve_telegram_chat_and_token(
        session, workspace_id, target_chat_id
    )

    if not chat_id or not token:
        reason = (
            "unauthorized_chat_id"
            if target_chat_id and not chat_id
            else "missing_chat_id_or_token"
        )
        logger.warning(
            "Telegram alert skipped: %s for workspace %s",
            reason,
            workspace_id,
        )
        return {
            "sent": False,
            "reason": reason,
            "text": text,
            "reply_markup": reply_markup,
        }

    try:
        client = TelegramClient(token=token)
        result = await client.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup,
        )
        logger.info(
            "Telegram lead alert sent successfully to chat_id=%s, msg_id=%s",
            chat_id,
            result.external_message_id,
        )
        return {
            "sent": True,
            "chat_id": chat_id,
            "message_id": result.external_message_id,
            "text": text,
        }
    except Exception as exc:
        logger.error("Failed to send Telegram lead alert: %s", exc)
        return {"sent": False, "error": str(exc), "text": text}
