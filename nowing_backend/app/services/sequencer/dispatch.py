"""Channel dispatch logic for sequence send steps."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import update

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
from app.services.sequencer.honorifics import (
    NEUTRAL_RESOLUTION,
    VietnamHonorificResolver,
    workspace_sender_demographics,
)
from app.services.sequencer.scheduling import calculate_step_eta, is_dispatch_curfew
from app.services.sequencer.templates import (
    interpolate_template_data,
    interpolate_template_variables,
)

logger = logging.getLogger(__name__)


class SequencerDispatchMixin:
    """Send-step dispatch helpers for email, telegram, and zalo channels."""

    def __init__(self) -> None:
        super().__init__()
        self.encryption: VerifiedContactEncryption
        self.billing_service: BillingEventService

    def _decrypt_field(self, value: Any) -> str | None:
        """Best-effort decrypt of an encrypted-at-rest contact field."""
        if not isinstance(value, str) or not value:
            return None
        try:
            if self.encryption.is_encrypted(value):
                return self.encryption.decrypt(value)
        except Exception:  # decrypt failure → omit field; never emit ciphertext
            return None
        return value

    async def _defer_step_for_curfew(
        self,
        session: Any,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        *,
        channel: str,
    ) -> SequenceEvent:
        """Decree 91 curfew: re-schedule the step to the next 08:05 ICT window.

        OCC-guarded: only reschedules while the enrollment is still in an
        active/scheduled state owned by this path — a concurrent opt-out or
        version bump must not be overwritten.
        """
        next_eta = calculate_step_eta(0)
        current_version = enrollment.version or 0
        res = await session.execute(
            update(SequenceEnrollment)
            .where(
                SequenceEnrollment.id == enrollment.id,
                SequenceEnrollment.workspace_id == enrollment.workspace_id,
                SequenceEnrollment.version == current_version,
                SequenceEnrollment.status.in_(
                    ["scheduled", "executing", "paused"]
                ),
            )
            .values(
                status="scheduled",
                scheduled_at=next_eta,
                version=current_version + 1,
                updated_at=datetime.now(UTC),
            )
        )
        deferred = getattr(res, "rowcount", 0) != 0
        if deferred:
            enrollment.status = "scheduled"
            enrollment.scheduled_at = next_eta
            enrollment.version = current_version + 1
        else:
            # Another path (e.g. inbound opt-out CAS) owns the enrollment —
            # skip the update rather than clobber its state.
            logger.info(
                "Curfew deferral skipped for enrollment %s: state/version "
                "changed concurrently",
                enrollment.id,
            )
            next_eta = None

        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="skipped",
            event_subtype="curfew_decree91",
            channel=channel,
            cost_micros=0,
            event_metadata={
                "reason": "curfew_decree91",
                "detail": "Dispatch halted 21:00-08:00 ICT per Decree 91/2020/NĐ-CP",
                "rescheduled_at": next_eta.isoformat() if next_eta else None,
            },
        )
        session.add(event)
        await session.commit()
        return event

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
            except Exception:  # decrypt failure → raw value fallback keeps dispatch attemptable
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
            except Exception:  # decrypt failure → raw value fallback keeps dispatch attemptable
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

        # AC-1/AC-2 (Story 37.2 / AD-116): deterministic honorific resolution,
        # injected under the {salutation} token for template interpolation.
        # Per-workspace sender profile (icp_criteria) overrides the global
        # SEQUENCER_SENDER_* env defaults.
        try:
            sender_birth_year, sender_gender = await workspace_sender_demographics(
                session, enrollment.workspace_id
            )
            honorific = VietnamHonorificResolver().resolve(
                lead=lead,
                contact=contact,
                profile={
                    "name": self._decrypt_field(getattr(contact, "name", None)),
                    "title": self._decrypt_field(getattr(contact, "title", None)),
                },
                sender_birth_year=sender_birth_year,
                sender_gender=sender_gender,
            )
        except Exception:  # honorific resolution must never block dispatch
            logger.exception("Honorific resolution failed for lead %s", lead.id)
            honorific = NEUTRAL_RESOLUTION

        context_vars = {
            "customer_name": getattr(lead, "contact_name", None)
            or getattr(lead, "company_name", None)
            or "Quý khách",
            "company": getattr(lead, "company_name", None) or "Doanh nghiệp",
            "property_title": (lead.custom_fields or {}).get("property_title", "")
            if lead.custom_fields
            else "",
            "consultant_phone": getattr(config, "CONSULTANT_PHONE", "0901234567"),
            **honorific.to_context_vars(),
        }

        # AC-5 (Story 37.5): inject the mini-pitch portal URL when the cadence
        # copy references {pitch_portal_url}. The build is idempotent — the
        # per-lead artifact is Redis-cached so repeat sends never rebuild.
        try:
            portal_url = await self._resolve_pitch_portal_url(
                session, lead, template_data
            )
            if portal_url:
                context_vars["pitch_portal_url"] = portal_url
        except Exception:  # portal injection must never block dispatch
            logger.exception(
                "pitch portal injection failed for lead %s", lead.id
            )

        # AC-4 (Story 37.2 / Decree 91/2020/NĐ-CP): hard halt 21:00-08:00 ICT.
        # Checked after consent/DNC/billing gates so those skip/fail outcomes
        # still take precedence; placed before any provider call so nothing is
        # dispatched during curfew.
        if is_dispatch_curfew():
            return await self._defer_step_for_curfew(
                session, sequence, step, enrollment, channel=step.channel
            )

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
            # AC-4: re-check per attempt — a step that started before 21:00
            # must not dispatch a fallback channel after the boundary.
            if is_dispatch_curfew():
                return await self._defer_step_for_curfew(
                    session, sequence, step, enrollment, channel=channel
                )
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
            except Exception as exc:  # per-channel dispatch failure → record error, try fallback channel
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
            # Inject {salutation} & other context vars into ZNS template data —
            # recursively, so nested dicts/lists carry no literal tokens.
            zalo_data = interpolate_template_data(zalo_data, context_vars)
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

    async def _resolve_pitch_portal_url(
        self,
        session: Any,
        lead: Lead,
        template_data: dict[str, Any],
    ) -> str | None:
        """Story 37.5 / AC-5: lazily build the lead's mini-pitch portal and
        return its public URL — only when the template actually references
        ``{pitch_portal_url}``.  None when the token is absent."""
        from app.services.pitch_portal import (
            ensure_pitch_portal,
            template_requests_pitch_portal,
        )

        if not template_requests_pitch_portal(template_data):
            return None
        # _get_redis_async lives on SequencerInboundMixin (combined on
        # SequencerService); fall back to the raw client for isolated use.
        get_redis = getattr(self, "_get_redis_async", None)
        if get_redis is not None:
            redis_client = await get_redis()
        else:
            from app.redis_client import get_redis_client

            redis_client = await get_redis_client()
        portal = await ensure_pitch_portal(session, redis_client, lead)
        return portal["url"]

    async def _send_email_async(self, to_email: str, subject: str, body: str) -> str:
        """Asynchronous wrapper around synchronous SMTP sender."""
        await asyncio.to_thread(
            _send_email_smtp, to_email=to_email, subject=subject, body=body
        )
        return f"msg_{uuid4().hex[:12]}"
