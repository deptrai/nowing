"""Channel dispatch logic for sequence send steps."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from app.alerts.engine.notify import _send_email_smtp
from app.config import config
from app.db import (
    Lead,
    Sequence,
    SequenceEnrollment,
    SequenceEvent,
    SequenceStep,
    VerifiedContact,
)
from app.gateway.accounts import account_token, get_or_create_system_telegram_account
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.zalo.zns_client import ZnsClient
from app.lead_intelligence.dnc.normalizer import (
    normalize_email,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.services import wallet_credit
from app.services.billing_event_service import BillingEventService
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
from app.services.sequencer.templates import interpolate_template_variables

logger = logging.getLogger(__name__)


class SequencerDispatchMixin:
    """Send-step dispatch helpers for email, telegram, and zalo channels."""

    def __init__(self) -> None:
        super().__init__()
        self.encryption: VerifiedContactEncryption
        self.billing_service: BillingEventService

    async def _send_email_dispatch(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
    ) -> str:
        """Dispatch email via SMTP and return provider message id."""
        return await self._send_email_async(
            to_email=to_email, subject=subject, body=body
        )

    async def _send_telegram_dispatch(
        self,
        session: Any,
        workspace_id: int,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> str:
        """Dispatch Telegram bot message for a workspace."""
        from sqlalchemy.ext.asyncio import AsyncSession

        if not isinstance(session, AsyncSession):
            raise TypeError("session must be an AsyncSession")

        account = await get_or_create_system_telegram_account(session)
        token = account_token(account)
        if not token:
            if not getattr(config, "TELEGRAM_SHARED_BOT_TOKEN", None):
                raise RuntimeError("missing_telegram_token")
            token = str(config.TELEGRAM_SHARED_BOT_TOKEN)
        adapter = TelegramAdapter(token)
        result = await adapter.send_message(
            external_peer_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )
        return result.external_message_id or f"tg_{uuid4().hex[:12]}"

    async def _send_zns_dispatch(
        self,
        session: Any,
        *,
        workspace_id: int,
        user_id: UUID | None,
        phone: str,
        template_id: str,
        template_data: dict[str, Any],
        lead_id: UUID,
    ) -> str:
        """Dispatch Zalo ZNS template for a workspace."""
        from sqlalchemy.ext.asyncio import AsyncSession

        if not isinstance(session, AsyncSession):
            raise TypeError("session must be an AsyncSession")

        cost_micros = int(getattr(config, "SEQUENCE_ZNS_COST_MICROS", 300))
        client = ZnsClient()
        res = await client.send_zns_template(
            session,
            workspace_id=workspace_id,
            phone=phone,
            template_id=template_id,
            template_data=template_data,
            user_id=user_id,
            lead_id=lead_id,
            cost_micros=cost_micros,
        )
        return res.get("msg_id") or f"zns_{uuid4().hex[:12]}"

    async def _handle_send_step(
        self,
        session: Any,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        lead: Lead,
    ) -> SequenceEvent:
        """AC-5 / AC-6 / AC-7: Multi-channel send step with fallback orchestration."""
        from sqlalchemy.ext.asyncio import AsyncSession

        if not isinstance(session, AsyncSession):
            # Allow fake test sessions to pass through without runtime type check.
            pass

        await self.validate_step_channel(step.channel)

        # 1. Resolve verified contact with external chat IDs for the primary channel.
        contact = await self._resolve_verified_contact(
            session, lead, channel=step.channel
        )
        if not contact or not contact.consent or not contact.is_valid:
            logger.info(
                "Skipping send step for lead %s: no consented contact for %s",
                lead.id,
                step.channel,
            )
            return await self._skip_step(
                session,
                sequence,
                step,
                enrollment,
                reason="no_consent",
                channel=step.channel,
            )

        # 2. Contact identifiers per channel
        raw_email = None
        raw_phone = None
        telegram_chat_id = None
        if step.channel == "email":
            try:
                raw_email = (
                    self.encryption.decrypt(contact.email)
                    if self.encryption.is_encrypted(contact.email)
                    else contact.email
                )
            except Exception:
                raw_email = contact.email
            if not raw_email:
                return await self._skip_step(
                    session,
                    sequence,
                    step,
                    enrollment,
                    reason="missing_email",
                    channel=step.channel,
                )
        else:
            try:
                raw_phone = (
                    self.encryption.decrypt(contact.phone)
                    if self.encryption.is_encrypted(contact.phone)
                    else contact.phone
                )
            except Exception:
                raw_phone = contact.phone
            if step.channel == "telegram":
                telegram_chat_id = (contact.external_chat_ids or {}).get(
                    "telegram_chat_id"
                )
                if not telegram_chat_id and raw_phone:
                    # Best-effort fallback: normalize phone is not a chat id, so fail.
                    pass
                if not telegram_chat_id:
                    return await self._skip_step(
                        session,
                        sequence,
                        step,
                        enrollment,
                        reason="missing_telegram_chat_id",
                        channel=step.channel,
                    )
            if step.channel == "zalo" and (not raw_phone or not str(raw_phone).strip()):
                return await self._skip_step(
                    session,
                    sequence,
                    step,
                    enrollment,
                    reason="missing_phone",
                    channel=step.channel,
                )

        # 3. Compliance & DNC pre-check
        is_allowed = await self.check_outbound_compliance(
            session,
            workspace_id=enrollment.workspace_id,
            phone=raw_phone,
            channel=step.channel,
            consent_status=lead.consent_status,
            legal_basis=lead.legal_basis,
            external_chat_ids=contact.external_chat_ids or {},
        )
        if not is_allowed:
            return await self._skip_step(
                session,
                sequence,
                step,
                enrollment,
                reason="compliance_or_dnc",
                channel=step.channel,
            )

        # 4. Wallet pre-check
        billing_spec = self.get_billing_event_for_step(step.channel)
        cost_micros = int(billing_spec["cost_micros"])
        attributed_user_id = sequence.created_by_user_id
        if not attributed_user_id:
            from app.db import Workspace

            ws = await session.get(Workspace, enrollment.workspace_id)
            attributed_user_id = ws.user_id if ws else None

        if cost_micros > 0 and attributed_user_id:
            try:
                await wallet_credit.check_balance(
                    session, attributed_user_id, cost_micros
                )
            except wallet_credit.InsufficientCreditsError:
                return await self._fail_step(
                    session,
                    sequence,
                    step,
                    enrollment,
                    reason="insufficient_credits",
                    channel=step.channel,
                    detail=f"requires {cost_micros} micros",
                )

        # 5. Template interpolation
        template_data = step.template or {}
        context_vars = {
            "customer_name": getattr(lead, "contact_name", None)
            or getattr(lead, "company_name", None)
            or "Quý khách",
            "company": getattr(lead, "company_name", None) or "Doanh nghiệp",
            "property_title": (lead.custom_fields or {}).get("property_title", "")
            if lead.custom_fields
            else "",
            "consultant_phone": getattr(config, "CONSULTANT_PHONE", "0901234567"),
        }

        # 6. Dispatch with fallback
        primary_channel = step.channel
        fallback_channels = step.fallback_channels or []
        channels_to_try = [primary_channel, *list(fallback_channels)]
        channels_to_try = list(
            dict.fromkeys(
                [c.strip().lower() for c in channels_to_try if c and c.strip()]
            )
        )

        last_error: str | None = None
        for channel in channels_to_try:
            try:
                await self.validate_step_channel(channel)
                msg_id, used_channel = await self._dispatch_single_channel(
                    session=session,
                    sequence=sequence,
                    step=step,
                    enrollment=enrollment,
                    lead=lead,
                    contact=contact,
                    channel=channel,
                    template_data=template_data,
                    context_vars=context_vars,
                    attributed_user_id=attributed_user_id,
                    cost_micros=cost_micros,
                )

                # 7. Success -> record event, advance, bill
                event = SequenceEvent(
                    workspace_id=enrollment.workspace_id,
                    client_id=enrollment.client_id,
                    enrollment_id=enrollment.id,
                    sequence_id=sequence.id,
                    step_id=step.id,
                    event_type="sent",
                    channel=used_channel,
                    cost_micros=cost_micros,
                    event_metadata={
                        "template_id": template_data.get("template_id"),
                        "fallback_used": used_channel != primary_channel,
                    },
                    provider_msg_id=msg_id,
                )
                session.add(event)
                await session.flush()

                await self._advance_to_next_step(session, sequence, step, enrollment)

                billing_spec = self.get_billing_event_for_step(used_channel)
                cost_micros = int(billing_spec["cost_micros"])
                event.cost_micros = cost_micros
                await self.billing_service.record_sequence_send(
                    session=session,
                    sequence_event_id=event.id,
                    event_type=billing_spec["event_type"],
                    workspace_id=enrollment.workspace_id,
                    client_id=enrollment.client_id,
                    user_id=attributed_user_id,
                    cost_micros=cost_micros,
                )

                # Ensure final commit for zero-cost sends and staged state.
                await session.commit()
                return event
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Channel %s failed for lead %s: %s. Trying fallback...",
                    channel,
                    lead.id,
                    exc,
                )

        # All channels failed
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="failed",
            event_subtype="all_channels_unavailable",
            channel=step.channel,
            cost_micros=0,
            event_metadata={"error": last_error or "all_channels_unavailable"},
        )
        session.add(event)
        enrollment.status = "failed"
        await session.commit()
        return event

    async def _dispatch_single_channel(
        self,
        *,
        session: Any,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        lead: Lead,
        contact: VerifiedContact,
        channel: str,
        template_data: dict[str, Any],
        context_vars: dict[str, Any],
        attributed_user_id: UUID | None,
        cost_micros: int,
    ) -> tuple[str, str]:
        """Dispatch one channel and return (provider_msg_id, used_channel)."""
        from sqlalchemy.ext.asyncio import AsyncSession

        if not isinstance(session, AsyncSession):
            # Allow fake test sessions to pass through without runtime type check.
            pass

        if channel == "email":
            raw_email = contact.email
            if not raw_email:
                raise ValueError("missing_email")
            if self.encryption.is_encrypted(raw_email):
                raw_email = self.encryption.decrypt(raw_email)
            norm_email = normalize_email(raw_email) or ""

            dnc_key = (
                getattr(config, "SECRET_KEY", None)
                or "nowing-secret-key-for-dnc-compliance-32"
            )
            dnc_svc = DncComplianceService(secret_key=dnc_key)
            dnc_result = await dnc_svc.is_blocked(
                workspace_id=enrollment.workspace_id,
                email=norm_email,
                session=session,
            )
            if dnc_result.is_blocked:
                raise ValueError("dnc_blocked")

            subject = interpolate_template_variables(
                template_data.get("subject", "Cơ hội hợp tác từ Nowing"),
                context_vars,
            )
            body = interpolate_template_variables(
                template_data.get("body", ""), context_vars
            )
            msg_id = await self._send_email_dispatch(
                to_email=norm_email, subject=subject, body=body
            )
            return msg_id, "email"

        if channel == "zalo":
            raw_phone = contact.phone
            if not raw_phone:
                raise ValueError("missing_phone")
            if self.encryption.is_encrypted(raw_phone):
                raw_phone = self.encryption.decrypt(raw_phone)
            phone = normalize_phone_e164(raw_phone) or raw_phone

            dnc_key = (
                getattr(config, "SECRET_KEY", None)
                or "nowing-secret-key-for-dnc-compliance-32"
            )
            dnc_svc = DncComplianceService(secret_key=dnc_key)
            dnc_result = await dnc_svc.is_blocked(
                workspace_id=enrollment.workspace_id,
                phone=phone,
                session=session,
            )
            if dnc_result.is_blocked:
                raise ValueError("dnc_blocked")

            zalo_template = template_data.get("template_id") or template_data.get(
                "zalo_template_id"
            )
            zalo_data = (
                template_data.get("template_data")
                or template_data.get("zalo_template_data")
                or {}
            )
            if not zalo_template:
                raise ValueError("missing_zalo_template_id")

            msg_id = await self._send_zns_dispatch(
                session=session,
                workspace_id=enrollment.workspace_id,
                user_id=attributed_user_id,
                phone=phone,
                template_id=str(zalo_template),
                template_data=zalo_data,
                lead_id=lead.id,
            )
            return msg_id, "zalo"

        if channel == "telegram":
            chat_id = (contact.external_chat_ids or {}).get("telegram_chat_id")
            if not chat_id:
                raise ValueError("missing_telegram_chat_id")

            dnc_key = (
                getattr(config, "SECRET_KEY", None)
                or "nowing-secret-key-for-dnc-compliance-32"
            )
            dnc_svc = DncComplianceService(secret_key=dnc_key)

            if contact.phone:
                raw_phone = contact.phone
                if self.encryption.is_encrypted(raw_phone):
                    raw_phone = self.encryption.decrypt(raw_phone)
                phone = normalize_phone_e164(raw_phone) or raw_phone
                dnc_result = await dnc_svc.is_blocked(
                    workspace_id=enrollment.workspace_id,
                    phone=phone,
                    session=session,
                )
                if dnc_result.is_blocked:
                    raise ValueError("dnc_blocked")

            if contact.email:
                raw_email = contact.email
                if self.encryption.is_encrypted(raw_email):
                    raw_email = self.encryption.decrypt(raw_email)
                norm_email = normalize_email(raw_email) or ""
                if norm_email:
                    dnc_result = await dnc_svc.is_blocked(
                        workspace_id=enrollment.workspace_id,
                        email=norm_email,
                        session=session,
                    )
                    if dnc_result.is_blocked:
                        raise ValueError("dnc_blocked")

            text = interpolate_template_variables(
                template_data.get("body", ""), context_vars
            )
            parse_mode = template_data.get("parse_mode")
            msg_id = await self._send_telegram_dispatch(
                session=session,
                workspace_id=enrollment.workspace_id,
                chat_id=str(chat_id),
                text=text,
                parse_mode=parse_mode,
            )
            return msg_id, "telegram"

        raise ValueError(f"unsupported_channel:{channel}")

    async def _send_email_async(self, to_email: str, subject: str, body: str) -> str:
        """Asynchronous wrapper around synchronous SMTP sender."""
        await asyncio.to_thread(
            _send_email_smtp, to_email=to_email, subject=subject, body=body
        )
        return f"msg_{uuid4().hex[:12]}"
