"""Compliance, billing, and verified-contact resolution helpers for sequencer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Lead,
    Sequence,
    SequenceEnrollment,
    SequenceEvent,
    SequenceStep,
    VerifiedContact,
)
from app.lead_intelligence.dnc.normalizer import normalize_phone_e164
from app.lead_intelligence.dnc.service import DncComplianceService
from app.services.billing_event_service import BillingEventService
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
from app.services.sequencer.constants import ALLOWED_OUTBOUND_CHANNELS, VN_TZ

logger = logging.getLogger(__name__)


class SequencerComplianceMixin:
    """Consent/DNC validation, billing, and contact resolution for send steps."""

    # AD-25 / AD-49: lead consent statuses that allow outbound communication
    ENROLLABLE_CONSENT_STATUSES = {"granted", "confirmed", "opted_in"}

    def __init__(self) -> None:
        super().__init__()
        self.encryption: VerifiedContactEncryption
        self.billing_service: BillingEventService

    async def validate_step_channel(self, channel: str) -> bool:
        """Validate outreach channel against allowed MVP channels (AD-41)."""
        allowed = getattr(
            config, "SEQUENCER_OUTBOUND_CHANNELS", ALLOWED_OUTBOUND_CHANNELS
        )
        if isinstance(allowed, str):
            allowed = [c.strip() for c in allowed.split(",") if c.strip()]
        allowed_lower = {c.lower() for c in allowed}
        if channel.lower() not in allowed_lower:
            from app.services.sequencer.constants import DeferredChannelError

            raise DeferredChannelError(
                f"Channel '{channel}' is deferred out of MVP (AD-41 / DEF-102). Only {allowed} supported."
            )
        # AD-41 / DEF-102 legal gate: Zalo requires explicit re-activation.
        if channel.lower() == "zalo" and not getattr(
            config, "AD_41_REACTIVATED", False
        ):
            from app.services.sequencer.constants import DeferredChannelError

            raise DeferredChannelError(
                "Channel 'zalo' is gated by AD-41 / DEF-102. Set AD_41_REACTIVATED=true after SCP sign-off."
            )
        return True

    def calculate_step_eta(
        self,
        target_dt: datetime | None = None,
        delay_seconds: int = 0,
        from_dt: datetime | None = None,
    ) -> datetime:
        """AC-3: Calculate step ETA respecting quiet hours (08:00 - 21:30 VN Time) & jitter."""
        from datetime import datetime

        base_dt = target_dt or from_dt or datetime.now(VN_TZ)
        from app.services.sequencer.scheduling import calculate_step_eta as _calc

        return _calc(delay_seconds=delay_seconds, from_dt=base_dt)

    async def check_outbound_compliance(
        self,
        session: AsyncSession,
        workspace_id: int,
        phone: str | None,
        channel: str,
        consent_status: str | None,
        legal_basis: str | None,
        external_chat_ids: dict[str, Any] | None = None,
    ) -> bool:
        """AC-4 / INV-24.2: Verify Consent & DNC Pre-check fail-closed."""
        if not legal_basis or not str(legal_basis).strip():
            return False
        if consent_status not in self.ENROLLABLE_CONSENT_STATUSES:
            return False

        external_chat_ids = external_chat_ids or {}

        # Fail-closed if the required channel identifier is missing.
        if channel == "zalo" and (not phone or not str(phone).strip()):
            return False
        if channel == "telegram" and not external_chat_ids.get("telegram_chat_id"):
            return False

        dnc_key = getattr(config, "SECRET_KEY", None)
        if not dnc_key:
            logger.error(
                "[SequencerService] SECRET_KEY is not configured — failing closed for DNC pre-check"
            )
            return False

        dnc_svc = DncComplianceService(secret_key=dnc_key)

        # Check DNC by email/phone domain/tax when available.
        if phone and str(phone).strip():
            normalized = normalize_phone_e164(str(phone).strip())
            if not normalized:
                return False
            dnc_result = await dnc_svc.is_blocked(
                workspace_id=workspace_id,
                phone=normalized,
                session=session,
            )
            if dnc_result.is_blocked:
                return False

        return True

    def get_billing_event_for_step(
        self, channel: str, event_type: str = "sent"
    ) -> dict[str, Any]:
        """AD-42 / AD-48 / AC-7: Return billing event specification."""
        if event_type == "meeting_booked":
            return {
                "event_type": "outcome_meeting_booked",
                "event_entity_type": "outcome_event",
                "cost_micros": 0,
            }

        channel_type_map = {
            "email": "email_send",
            "zalo": "zns_send",
            "telegram": "telegram_send",
        }
        cost_map = {
            "email": getattr(config, "SEQUENCE_EMAIL_COST_MICROS", 500),
            "zalo": getattr(config, "SEQUENCE_ZNS_COST_MICROS", 300),
            "telegram": getattr(config, "SEQUENCE_TELEGRAM_COST_MICROS", 0),
        }
        return {
            "event_type": channel_type_map.get(channel, f"{channel}_send"),
            "event_entity_type": "sequence_event",
            "cost_micros": cost_map.get(channel, 0),
        }

    async def _resolve_verified_contact(
        self,
        session: AsyncSession,
        lead: Lead,
        channel: str = "email",
    ) -> VerifiedContact | None:
        """Resolve highest-confidence consented VerifiedContact for given lead and channel."""
        stmt = (
            select(VerifiedContact)
            .where(
                VerifiedContact.lead_id == lead.id,
                VerifiedContact.workspace_id == lead.workspace_id,
                VerifiedContact.consent.is_(True),
                VerifiedContact.is_valid.is_(True),
            )
            .order_by(
                VerifiedContact.confidence.desc(), VerifiedContact.created_at.desc()
            )
        )
        contact = (await session.execute(stmt)).scalars().first()
        if not contact:
            return None

        if channel == "email" and not contact.email:
            return None
        if channel == "telegram" and not (contact.external_chat_ids or {}).get(
            "telegram_chat_id"
        ):
            # Fallback: if phone-based chat id exists in the lead, accept it later.
            return None
        if channel == "zalo" and not contact.phone:
            return None

        return contact

    async def _fail_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        *,
        reason: str,
        channel: str,
        detail: str | None = None,
    ) -> SequenceEvent:
        """Record a failed send step and stop the enrollment."""
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="failed",
            event_subtype=reason,
            channel=channel,
            cost_micros=0,
            event_metadata={"reason": reason, "detail": detail},
        )
        session.add(event)
        enrollment.status = "failed"
        enrollment.scheduled_at = None
        enrollment.updated_at = datetime.now(UTC)
        await session.commit()
        return event

    async def _skip_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        *,
        reason: str,
        channel: str,
        detail: str | None = None,
    ) -> SequenceEvent:
        """Record a skipped send step and advance enrollment."""
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="skipped",
            event_subtype=reason,
            channel=channel,
            cost_micros=0,
            event_metadata={"reason": reason, "detail": detail},
        )
        session.add(event)
        if reason == "dnc_blocked":
            enrollment.status = "unsubscribed"
        await self._advance_to_next_step(session, sequence, step, enrollment)
        await session.commit()
        return event
