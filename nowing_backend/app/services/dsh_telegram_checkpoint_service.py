"""DSH Telegram Interactive Checkpoint Service (Story 26.6).

Builds 3-second glanceable cards for high-fit leads discovered during DSH ingestion,
and handles interactive 1-click unlock, dossier expansion, skip, and 24h auto-refund callbacks.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    DshMission,
    ExternalChatAccount,
    ExternalChatBinding,
    ExternalChatHealthStatus,
    Lead,
    PhoneWaterfallLog,
    TelegramCheckpointMessage,
    User,
    VerifiedContact,
)
from app.gateway.accounts import account_token
from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.telegram.formatting import escape_markdown_v2
from app.services.billing_event_service import BillingEventService
from app.services.contact_unlock_service import ContactUnlockService
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.phone_waterfall_service import PhoneWaterfallService
from app.services.pii.mask import mask_phone
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logger = logging.getLogger(__name__)


class DshTelegramCheckpointService:
    """Service orchestrating Telegram lead cards and callback actions."""

    def __init__(
        self,
        unlock_service: ContactUnlockService | None = None,
        billing_service: BillingEventService | None = None,
        encryption: VerifiedContactEncryption | None = None,
    ) -> None:
        self.unlock_service = unlock_service or ContactUnlockService()
        self.billing_service = billing_service or BillingEventService()
        self.enc = encryption or VerifiedContactEncryption()

    def _decrypt_or_passthrough(self, value: str | None) -> str | None:
        if not value:
            return None
        if self.enc.is_encrypted(value):
            try:
                return self.enc.decrypt(value)
            except Exception:
                return None
        return value

    def build_checkpoint_card(
        self,
        lead: Lead | Any,
        contact: VerifiedContact | Any,
        callback_token: str,
    ) -> tuple[str, dict[str, Any]]:
        """Build MarkdownV2 card and inline keyboard for a high-fit lead."""
        raw_company = getattr(lead, "company_name", None) or "Doanh nghiệp"
        company_escaped = escape_markdown_v2(str(raw_company))

        fit_score = getattr(lead, "fit_score", None)
        if fit_score is None:
            fit_score = 0
        source = escape_markdown_v2(str(getattr(lead, "source", "") or "Web"))
        domain = escape_markdown_v2(str(getattr(lead, "domain", "") or "nowing.net"))

        raw_phone = self._decrypt_or_passthrough(
            getattr(contact, "phone", None) or getattr(lead, "phone", None)
        )
        masked_phone_str = mask_phone(raw_phone) if raw_phone else "Chưa có SĐT"
        masked_phone_escaped = escape_markdown_v2(masked_phone_str)

        card_text = (
            f"🎯 *Lead mới — {company_escaped}*\n"
            f"📊 Fit score: `{fit_score}/100`\n"
            f"📞 SĐT: `{masked_phone_escaped}`\n"
            f"🌐 Nguồn: `{source}` \\| `{domain}`"
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "🔓 Mở khóa SĐT",
                        "callback_data": f"dsh:unlock:{callback_token}",
                    },
                    {
                        "text": "🌐 Xem Dossier",
                        "callback_data": f"dsh:dossier:{callback_token}",
                    },
                    {
                        "text": "❌ Bỏ qua",
                        "callback_data": f"dsh:skip:{callback_token}",
                    },
                ]
            ]
        }
        return card_text, reply_markup

    def select_high_fit_lead(
        self,
        leads: list[Lead | dict[str, Any] | Any],
        threshold: int | None = None,
    ) -> Lead | dict[str, Any] | Any | None:
        """Select the highest-fit lead with fit_score >= threshold having a phone number."""
        target_threshold = (
            threshold
            if threshold is not None
            else getattr(config, "DSH_TELEGRAM_FIT_SCORE_THRESHOLD", 80)
        )

        candidates = []
        for lead in leads:
            score = (
                lead.get("fit_score")
                if isinstance(lead, dict)
                else getattr(lead, "fit_score", None)
            )
            phone = (
                lead.get("phone")
                if isinstance(lead, dict)
                else getattr(lead, "phone", None)
            )
            if score is not None and score >= target_threshold and phone:
                candidates.append(lead)

        if not candidates:
            return None

        # Sort by fit_score DESC (normalize to float to avoid mixed-type crashes)
        def _fit_score(item: Any) -> float:
            if isinstance(item, dict):
                raw = item.get("fit_score")
            else:
                raw = getattr(item, "fit_score", None)
            try:
                return float(raw) if raw is not None else 0.0
            except (TypeError, ValueError):
                return 0.0

        candidates.sort(key=_fit_score, reverse=True)
        return candidates[0]

    def should_send_telegram_notification(self, user: User | Any | None) -> bool:
        """Check if user has not explicitly disabled DSH lead telegram notifications."""
        if user is None:
            return False
        prefs = getattr(user, "notification_preferences", None)
        if not prefs or not isinstance(prefs, dict):
            return True
        dsh_prefs = prefs.get("dsh_high_fit_lead")
        if isinstance(dsh_prefs, dict):
            return bool(dsh_prefs.get("telegram", True))
        if isinstance(dsh_prefs, bool):
            return dsh_prefs
        return True

    async def notify_high_fit_lead(
        self,
        session: AsyncSession,
        workspace_id: int,
        mission_id: UUID,
        lead_id: UUID,
        contact_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Internal worker endpoint logic: send Telegram card and store checkpoint message."""
        mission = await session.get(DshMission, mission_id)
        if mission is None or mission.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found in workspace",
            )

        user_id = mission.user_id
        if user_id is None:
            return {"status": "skipped", "reason": "mission_has_no_user"}

        user = await session.get(User, user_id)
        if not self.should_send_telegram_notification(user):
            return {"status": "skipped", "reason": "preference_disabled"}

        # Find active Telegram binding for this user + workspace
        binding_stmt = (
            select(ExternalChatBinding)
            .join(
                ExternalChatAccount,
                ExternalChatBinding.account_id == ExternalChatAccount.id,
            )
            .where(
                ExternalChatBinding.workspace_id == workspace_id,
                ExternalChatBinding.user_id == user_id,
                ExternalChatBinding.state == "bound",
                ExternalChatBinding.revoked_at.is_(None),
                ExternalChatBinding.suspended_at.is_(None),
                ExternalChatAccount.platform == "telegram",
                ExternalChatAccount.health_status != ExternalChatHealthStatus.FAILING.value,
                ExternalChatAccount.suspended_at.is_(None),
            )
            .order_by(desc(ExternalChatBinding.updated_at))
        )
        binding = (await session.execute(binding_stmt)).scalars().first()
        if binding is None or not binding.external_peer_id:
            return {"status": "skipped", "reason": "no_active_telegram_binding"}

        # Load lead
        lead = (
            await session.execute(
                select(Lead).where(
                    Lead.id == lead_id, Lead.workspace_id == workspace_id
                )
            )
        ).scalar_one_or_none()
        if lead is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found",
            )

        # Resolve contact
        if contact_id is not None:
            contact = (
                await session.execute(
                    select(VerifiedContact).where(
                        VerifiedContact.id == contact_id,
                        VerifiedContact.workspace_id == workspace_id,
                        VerifiedContact.lead_id == lead_id,
                    )
                )
            ).scalar_one_or_none()
        else:
            contact = (
                (
                    await session.execute(
                        select(VerifiedContact)
                        .where(
                            VerifiedContact.lead_id == lead_id,
                            VerifiedContact.workspace_id == workspace_id,
                            VerifiedContact.phone.isnot(None),
                            VerifiedContact.is_valid.is_(True),
                            VerifiedContact.consent_status != "withdrawn",
                        )
                        .order_by(VerifiedContact.created_at.asc())
                    )
                )
                .scalars()
                .first()
            )

        if contact is None:
            return {"status": "skipped", "reason": "no_verified_contact"}

        if not contact.is_valid or contact.consent_status == "withdrawn":
            return {"status": "skipped", "reason": "contact_withdrawn"}

        # Max leads per mission guard.
        max_leads = getattr(config, "DSH_TELEGRAM_MAX_LEADS_PER_MISSION", 1)
        existing_count = (
            await session.execute(
                select(func.count(TelegramCheckpointMessage.id)).where(
                    TelegramCheckpointMessage.mission_id == mission_id,
                    TelegramCheckpointMessage.workspace_id == workspace_id,
                    TelegramCheckpointMessage.status != "failed",
                )
            )
        ).scalar() or 0
        if existing_count >= max_leads:
            return {"status": "skipped", "reason": "max_leads_per_mission"}

        # Idempotency: one non-failed checkpoint card per mission
        existing_checkpoint = (
            await session.execute(
                select(TelegramCheckpointMessage)
                .where(
                    TelegramCheckpointMessage.mission_id == mission_id,
                    TelegramCheckpointMessage.workspace_id == workspace_id,
                    TelegramCheckpointMessage.status != "failed",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if existing_checkpoint is not None:
            return {"status": "skipped", "reason": "already_notified"}

        # Generate unique 16-24 char URL-safe token
        callback_token = secrets.token_urlsafe(16)[:24]

        # Persist checkpoint message row in DB first (external_message_id=None initially)
        checkpoint_msg = TelegramCheckpointMessage(
            workspace_id=workspace_id,
            mission_id=mission_id,
            lead_id=lead_id,
            contact_id=contact.id,
            user_id=user_id,
            callback_token=callback_token,
            status="sent",
            external_peer_id=binding.external_peer_id,
        )
        session.add(checkpoint_msg)
        await session.flush()

        # Resolve bot token and send Telegram message
        account = await session.get(ExternalChatAccount, binding.account_id)
        token = account_token(account) if account else None
        if not token:
            checkpoint_msg.status = "failed"
            await session.commit()
            return {"status": "sent_failed", "reason": "missing_telegram_token"}

        card_text, reply_markup = self.build_checkpoint_card(
            lead, contact, callback_token
        )
        adapter = TelegramAdapter(token)
        try:
            res = await adapter.send_message(
                external_peer_id=binding.external_peer_id,
                text=card_text,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )
            if res and res.external_message_id:
                checkpoint_msg.external_message_id = str(res.external_message_id)
            await session.commit()
            return {
                "status": "sent",
                "callback_token": callback_token,
                "contact_id": str(contact.id),
                "message_id": checkpoint_msg.external_message_id,
            }
        except Exception as exc:
            logger.warning(
                "Failed to send Telegram checkpoint card: %s", exc, exc_info=True
            )
            checkpoint_msg.status = "failed"
            await session.commit()
            return {"status": "sent_failed", "error": str(exc)}

    # ========================================================================
    # Callback Handlers (dsh:unlock / dsh:dossier / dsh:skip / dsh:refund)
    # ========================================================================

    async def handle_unlock_callback(
        self,
        *,
        session: AsyncSession,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        binding: ExternalChatBinding,
        callback_token: str,
        callback_query_id: str | None = None,
    ) -> None:
        """Handle 1-click unlock callback: bill, decrypt PII, and edit message."""
        checkpoint = (
            await session.execute(
                select(TelegramCheckpointMessage)
                .where(
                    TelegramCheckpointMessage.callback_token == callback_token,
                    TelegramCheckpointMessage.workspace_id == binding.workspace_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

        if checkpoint is None:
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Không tìm thấy thông tin lead.",
                    show_alert=True,
                )
            return

        contact = (
            await session.execute(
                select(VerifiedContact)
                .where(
                    VerifiedContact.id == checkpoint.contact_id,
                    VerifiedContact.workspace_id == binding.workspace_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

        if contact is None:
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Không tìm thấy liên hệ.",
                    show_alert=True,
                )
            return

        if checkpoint.status in ("unlocked", "refunded", "dismissed"):
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Thao tác đã hoàn tất.",
                )
            return

        user_id = binding.user_id or checkpoint.user_id
        lead = await session.get(Lead, (checkpoint.lead_id, binding.workspace_id))

        try:
            result = await self.unlock_service.unlock_contact(
                session=session,
                workspace_id=binding.workspace_id,
                contact=contact,
                user_id=user_id,
                lead=lead,
                reason="telegram_unlock",
            )
            checkpoint.status = "unlocked"
            if checkpoint.unlocked_at is None:
                checkpoint.unlocked_at = datetime.now(UTC)
            await session.commit()

            # Success text and buttons
            unmasked_phone = result.phone or "Chưa có SĐT"
            phone_escaped = escape_markdown_v2(unmasked_phone)
            success_text = f"✅ *Đã mở khóa SĐT — {phone_escaped}*\n💳 `-1.5 credits`"

            phone_digits = "".join(c for c in unmasked_phone if c.isdigit())
            buttons = []
            if len(phone_digits) >= 9:
                buttons.append(
                    {"text": "� Gọi điện", "url": f"tel:{phone_digits}"}
                )
                buttons.append(
                    {"text": "�💬 Zalo", "url": f"https://zalo.me/{phone_digits}"}
                )
            buttons.append(
                {
                    "text": "🛡️ Báo số sai / Hoàn tiền",
                    "callback_data": f"dsh:refund:{callback_token}",
                }
            )
            reply_markup = {"inline_keyboard": [buttons]}

            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=success_text,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup,
                )

            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Đã mở khóa thành công!",
                )
        except InsufficientCreditsError:
            err_text = "❌ *Không đủ credits\\. Nạp thêm tại dashboard để tiếp tục\\.*"
            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=err_text,
                    parse_mode="MarkdownV2",
                    reply_markup={"inline_keyboard": []},
                )
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Không đủ credits để mở khóa.",
                    show_alert=True,
                )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                err_text = "❌ *Số điện thoại bị chặn bởi DNC\\.*"
                alert_text = "Số điện thoại bị chặn bởi DNC."
            elif exc.status_code == status.HTTP_409_CONFLICT:
                err_text = "❌ *Liên hệ này đã bị rút lại đồng ý hoặc đánh dấu không hợp lệ\\.*"
                alert_text = "Liên hệ này đã bị rút lại đồng ý hoặc đánh dấu không hợp lệ."
            elif exc.status_code == status.HTTP_402_PAYMENT_REQUIRED:
                err_text = "❌ *Không đủ credits\\. Nạp thêm tại dashboard\\.*"
                alert_text = "Không đủ credits để mở khóa."
            else:
                err_text = "❌ *Không thể mở khóa liên hệ này\\.*"
                alert_text = "Không thể mở khóa liên hệ này."

            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=err_text,
                    parse_mode="MarkdownV2",
                    reply_markup={"inline_keyboard": []},
                )
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text=alert_text,
                    show_alert=True,
                )

    async def handle_dossier_callback(
        self,
        *,
        session: AsyncSession,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        binding: ExternalChatBinding,
        callback_token: str,
        callback_query_id: str | None = None,
    ) -> None:
        """Handle dossier expansion callback."""
        checkpoint = (
            await session.execute(
                select(TelegramCheckpointMessage).where(
                    TelegramCheckpointMessage.callback_token == callback_token,
                    TelegramCheckpointMessage.workspace_id == binding.workspace_id,
                )
            )
        ).scalar_one_or_none()

        if checkpoint is None:
            if callback_query_id:
                await adapter.answer_callback_query(callback_query_id=callback_query_id)
            return

        lead = await session.get(Lead, (checkpoint.lead_id, binding.workspace_id))
        contact = await session.get(VerifiedContact, checkpoint.contact_id)
        if lead is None or contact is None:
            if callback_query_id:
                await adapter.answer_callback_query(callback_query_id=callback_query_id)
            return

        company_name = escape_markdown_v2(
            str(getattr(lead, "company_name", "") or "Doanh nghiệp")
        )
        domain = escape_markdown_v2(str(getattr(lead, "domain", "") or "nowing.net"))
        fit_score = getattr(lead, "fit_score", 0) or 0
        intent_score = getattr(lead, "intent_score", None)
        intent_str = str(intent_score) if intent_score is not None else "N/A"
        source_url = escape_markdown_v2(
            str(getattr(lead, "source_url", "") or "https://nowing.net")
        )

        base_url = (
            getattr(config, "NEXT_FRONTEND_URL", "") or "http://localhost:3000"
        ).rstrip("/")
        deep_link = f"{base_url}/workspaces/{binding.workspace_id}/leads/{lead.id}"
        deep_link_escaped = escape_markdown_v2(deep_link)

        dossier_text = (
            f"🎯 *Dossier — {company_name}*\n"
            f"🏢 Domain: `{domain}`\n"
            f"📊 Fit: `{fit_score}` \\| Intent: `{intent_str}`\n"
            f"🔗 Nguồn: {source_url}\n"
            f"👉 [Mở trong Nowing]({deep_link_escaped})"
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "🔓 Mở khóa SĐT",
                        "callback_data": f"dsh:unlock:{callback_token}",
                    },
                    {
                        "text": "❌ Bỏ qua",
                        "callback_data": f"dsh:skip:{callback_token}",
                    },
                ]
            ]
        }

        peer_id = event.external_peer_id or checkpoint.external_peer_id
        msg_id = event.external_message_id or checkpoint.external_message_id
        if peer_id and msg_id:
            await adapter.edit_message(
                external_peer_id=peer_id,
                external_message_id=msg_id,
                text=dossier_text,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )

        if callback_query_id:
            await adapter.answer_callback_query(callback_query_id=callback_query_id)

    async def handle_skip_callback(
        self,
        *,
        session: AsyncSession,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        binding: ExternalChatBinding,
        callback_token: str,
        callback_query_id: str | None = None,
    ) -> None:
        """Handle skip callback: mark dismissed and clear buttons."""
        checkpoint = (
            await session.execute(
                select(TelegramCheckpointMessage)
                .where(
                    TelegramCheckpointMessage.callback_token == callback_token,
                    TelegramCheckpointMessage.workspace_id == binding.workspace_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

        if checkpoint is None:
            if callback_query_id:
                await adapter.answer_callback_query(callback_query_id=callback_query_id)
            return

        if checkpoint.status in ("unlocked", "refunded"):
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Lead này đã được xử lý.",
                )
            return

        checkpoint.status = "dismissed"
        await session.commit()

        dismiss_text = "❌ *Bạn đã bỏ qua lead này\\.*"
        peer_id = event.external_peer_id or checkpoint.external_peer_id
        msg_id = event.external_message_id or checkpoint.external_message_id
        if peer_id and msg_id:
            await adapter.edit_message(
                external_peer_id=peer_id,
                external_message_id=msg_id,
                text=dismiss_text,
                parse_mode="MarkdownV2",
                reply_markup={"inline_keyboard": []},
            )

        if callback_query_id:
            await adapter.answer_callback_query(
                callback_query_id=callback_query_id,
                text="Đã bỏ qua lead.",
            )

    async def _verify_phone_is_invalid(
        self,
        session: AsyncSession,
        contact_id: UUID,
        phone: str | None,
    ) -> bool:
        """Check if phone number is confirmed invalid via recent log or carrier heuristic."""
        # 1. Check most recent PhoneWaterfallLog
        log_stmt = (
            select(PhoneWaterfallLog)
            .where(PhoneWaterfallLog.contact_id == contact_id)
            .order_by(desc(PhoneWaterfallLog.created_at))
        )
        latest_log = (await session.execute(log_stmt)).scalars().first()
        if latest_log is not None:
            if latest_log.status in ("failed", "invalid"):
                return True
            if latest_log.status in ("success", "valid"):
                return False

        # 2. Carrier/HLR heuristic via PhoneWaterfallService as a fallback.
        if not phone:
            return True
        phone_digits = "".join(c for c in phone if c.isdigit())
        if len(phone_digits) < 9:
            return True
        try:
            waterfall = PhoneWaterfallService(session)
            result = await waterfall._resolve_tier_3_carrier_hlr(None, phone)
            if result.phone:
                return False
        except Exception:
            logger.warning(
                "Could not run phone verification for refund of contact %s",
                contact_id,
                exc_info=True,
            )
        return True

    async def handle_refund_callback(
        self,
        *,
        session: AsyncSession,
        adapter: TelegramAdapter,
        event: ParsedInboundEvent,
        binding: ExternalChatBinding,
        callback_token: str,
        callback_query_id: str | None = None,
    ) -> None:
        """Handle 1-click auto-refund for invalid numbers."""
        checkpoint = (
            await session.execute(
                select(TelegramCheckpointMessage)
                .where(
                    TelegramCheckpointMessage.callback_token == callback_token,
                    TelegramCheckpointMessage.workspace_id == binding.workspace_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

        if checkpoint is None:
            if callback_query_id:
                await adapter.answer_callback_query(callback_query_id=callback_query_id)
            return

        user_id = binding.user_id or checkpoint.user_id
        contact = await session.get(VerifiedContact, checkpoint.contact_id)

        if checkpoint.status != "unlocked" or checkpoint.unlocked_at is None:
            err_text = "❌ *Không thể hoàn tiền: chưa mở khóa.*"
            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=err_text,
                    parse_mode="MarkdownV2",
                    reply_markup={"inline_keyboard": []},
                )
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Không thể hoàn tiền: chưa mở khóa.",
                    show_alert=True,
                )
            return

        # 1. SLA check (24h)
        window_hours = getattr(config, "DSH_TELEGRAM_REFUND_WINDOW_HOURS", 24)
        if checkpoint.unlocked_at and datetime.now(
            UTC
        ) - checkpoint.unlocked_at > timedelta(hours=window_hours):
            err_text = "❌ *Đã hết hạn 24h để báo số sai\\.*"
            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=err_text,
                    parse_mode="MarkdownV2",
                    reply_markup={"inline_keyboard": []},
                )
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Đã hết hạn 24h để báo số sai.",
                    show_alert=True,
                )
            return

        # 2. Verify number is actually invalid
        phone_val = (
            self._decrypt_or_passthrough(getattr(contact, "phone", None))
            if contact
            else None
        )
        is_invalid = await self._verify_phone_is_invalid(
            session, checkpoint.contact_id, phone_val
        )
        if not is_invalid:
            active_text = "❌ *Không thể hoàn tiền: số điện thoại vẫn hoạt động\\.*"
            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=active_text,
                    parse_mode="MarkdownV2",
                )
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Số điện thoại vẫn hoạt động.",
                    show_alert=True,
                )
            return

        # 3. Attempt 24h refund via BillingEventService
        try:
            await self.billing_service.record_contact_unlock_refund_24h(
                session,
                verified_contact_id=checkpoint.contact_id,
                workspace_id=binding.workspace_id,
                user_id=user_id,
                refund_window_hours=window_hours,
            )
            checkpoint.status = "refunded"
            checkpoint.refunded_at = datetime.now(UTC)
            await session.commit()

            refund_text = "✅ *Đã hoàn tiền \\+1\\.5 credits — SĐT đã được đánh dấu không hợp lệ\\.*"
            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=refund_text,
                    parse_mode="MarkdownV2",
                    reply_markup={"inline_keyboard": []},
                )
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Đã hoàn tiền +1.5 credits!",
                )
        except ValueError as exc:
            err_msg = str(exc)
            if "auto-refund budget cap exhausted" in err_msg:
                err_text = "❌ *Không thể hoàn tiền: đã hết hạn mức hoàn tiền tự động tháng này\\.*"
                alert_text = "Đã hết hạn mức hoàn tiền tự động tháng này."
            elif "24h refund window expired" in err_msg:
                err_text = "❌ *Đã hết hạn 24h để báo số sai\\.*"
                alert_text = "Đã hết hạn 24h để báo số sai."
            elif "relock window expired" in err_msg or "already relocked" in err_msg:
                err_text = "❌ *Không thể hoàn tiền: liên hệ đã được xử lý relock.*"
                alert_text = "Không thể hoàn tiền: liên hệ đã được xử lý relock."
            else:
                err_text = "❌ *Không thể hoàn tiền cho liên hệ này\\.*"
                alert_text = "Không thể hoàn tiền cho liên hệ này."

            peer_id = event.external_peer_id or checkpoint.external_peer_id
            msg_id = event.external_message_id or checkpoint.external_message_id
            if peer_id and msg_id:
                await adapter.edit_message(
                    external_peer_id=peer_id,
                    external_message_id=msg_id,
                    text=err_text,
                    parse_mode="MarkdownV2",
                    reply_markup={"inline_keyboard": []},
                )
            if callback_query_id:
                await adapter.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text=alert_text,
                    show_alert=True,
                )
