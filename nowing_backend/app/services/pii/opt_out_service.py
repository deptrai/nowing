"""PII opt-out / Right-to-be-Forgotten service (Story 26.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    BillingEvent,
    GlobalDncRecord,
    VerifiedContact,
    WorkspaceDncRecord,
)
from app.lead_intelligence.dnc.normalizer import (
    compute_email_hmac,
    compute_phone_hmac,
    normalize_email,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.services import wallet_credit
from app.services.workspace_credit_service import WorkspaceCreditService

_REFUND_AMOUNT_MICROS = 1_500


@dataclass
class OptOutResult:
    """Result of a PII opt-out request."""

    purged_contact_count: int
    refunded_micros: int
    dnc_record_id: UUID | None = None


def _anonymize_contact(contact: VerifiedContact) -> None:
    """Irreversibly purge PII fields and mark consent as withdrawn."""
    contact.name = None
    contact.title = None
    contact.email = None
    contact.phone = None
    contact.phone_hmac = None
    contact.email_hmac = None
    contact.is_unlocked = False
    contact.consent = False
    contact.consent_status = "withdrawn"
    contact.legal_basis = "opt_out"


def _append_opt_out_audit_log(
    contact: VerifiedContact,
    *,
    actor_id: UUID,
    ip_address: str | None,
    reason: str | None,
) -> None:
    if contact.pii_access_audit_logs is None:
        contact.pii_access_audit_logs = []
    contact.pii_access_audit_logs.append(
        {
            "access_type": "opt_out_purged",
            "actor_id": str(actor_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "ip_address": ip_address,
            "reason": reason or "Right to be forgotten",
        }
    )


async def _find_original_unlock_billing_event(
    session: AsyncSession,
    verified_contact_id: UUID,
    workspace_id: int,
) -> BillingEvent | None:
    """Return the original contact_unlock BillingEvent for a contact."""
    result = await session.execute(
        select(BillingEvent).where(
            BillingEvent.workspace_id == workspace_id,
            BillingEvent.event_entity_type == "verified_contact",
            BillingEvent.event_type == "contact_unlock",
            BillingEvent.event_id == verified_contact_id,
        )
    )
    event = result.scalar_one_or_none()
    if getattr(event, "event_type", None) != "contact_unlock":
        return None
    return event


async def _count_refundable_unlocks_this_cycle(
    session: AsyncSession,
    workspace_id: int,
    cost_micros: int = _REFUND_AMOUNT_MICROS,
) -> int:
    """Remaining contact-unlock refund slots for this workspace in the current cycle.

    Cap = 15% of total unlocked contacts. The cycle is monthly; for simplicity we
    count refund events in the current calendar month.
    """
    if cost_micros <= 0:
        return 0

    total_unlocked = len(
        [
            c
            for c in (
                await session.execute(
                    select(VerifiedContact).where(
                        VerifiedContact.workspace_id == workspace_id,
                        VerifiedContact.is_unlocked.is_(True),
                    )
                )
            )
            .scalars()
            .all()
            if getattr(c, "is_unlocked", False)
        ]
    )

    allowed = max(1, int(total_unlocked * 0.15))

    now = datetime.now(UTC)
    already_refunded = len(
        [
            e
            for e in (
                await session.execute(
                    select(BillingEvent).where(
                        BillingEvent.workspace_id == workspace_id,
                        BillingEvent.event_entity_type == "verified_contact",
                        BillingEvent.event_type == "contact_unlock_refund",
                        BillingEvent.created_at
                        >= datetime(now.year, now.month, 1, tzinfo=UTC),
                    )
                )
            )
            .scalars()
            .all()
            if getattr(e, "event_type", None) == "contact_unlock_refund"
        ]
    )

    return max(0, allowed - already_refunded)


async def _credit_user_wallet(
    session: AsyncSession,
    user_id: UUID,
    amount_micros: int,
) -> None:
    """Credit a user wallet for an opt-out refund."""
    await wallet_credit.apply_credit(session, user_id, amount_micros)


async def _decrement_member_monthly_spent(
    session: AsyncSession,
    *,
    workspace_id: int,
    user_id: UUID,
    amount_micros: int,
) -> None:
    """Decrement the member's monthly spent counter without touching workspace balance."""
    credit_svc = WorkspaceCreditService(session=session)
    await credit_svc.refund_member_spend(
        workspace_id=workspace_id,
        user_id=user_id,
        amount_micros=amount_micros,
    )


class OptOutService:
    """Process PII opt-out requests per PDPD Decree 13/2023/ND-CP."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _refund_credit(
        self,
        contact: VerifiedContact,
        original_event: BillingEvent,
        workspace_id: int,
    ) -> int:
        """Refund one contact unlock and return refunded micros."""
        payer_id = original_event.user_id
        if payer_id is None:
            # Fallback to the actor; should not happen for valid unlock events.
            return 0

        await _credit_user_wallet(self.session, payer_id, _REFUND_AMOUNT_MICROS)
        await _decrement_member_monthly_spent(
            self.session,
            workspace_id=workspace_id,
            user_id=payer_id,
            amount_micros=_REFUND_AMOUNT_MICROS,
        )

        event = BillingEvent(
            workspace_id=workspace_id,
            user_id=payer_id,
            event_entity_type="verified_contact",
            event_type="contact_unlock_refund",
            event_id=contact.id,
            cost_micros=-_REFUND_AMOUNT_MICROS,
            currency="USD",
            cost_basis="actual",
        )
        self.session.add(event)
        return _REFUND_AMOUNT_MICROS

    async def _ensure_dnc_record(
        self,
        *,
        workspace_id: int,
        record_type: str,
        value: str,
        value_hmac: str,
        reason: str | None,
        global_scope: bool,
    ) -> WorkspaceDncRecord | GlobalDncRecord:
        if global_scope:
            # Global opt-out requires superadmin scope; store globally.
            record = GlobalDncRecord(
                id=uuid4(),
                record_type=record_type,
                value=value,
                value_hmac=value_hmac,
                reason=reason or "Right to be forgotten",
                source="opt_out",
            )
            self.session.add(record)
            return record

        existing = (
            await self.session.execute(
                select(WorkspaceDncRecord).where(
                    WorkspaceDncRecord.workspace_id == workspace_id,
                    WorkspaceDncRecord.record_type == record_type,
                    WorkspaceDncRecord.value_hmac == value_hmac,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.reason = reason or "Right to be forgotten"
            existing.source = "opt_out"
            return existing

        record = WorkspaceDncRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            record_type=record_type,
            value=value,
            value_hmac=value_hmac,
            reason=reason or "Right to be forgotten",
            source="opt_out",
        )
        self.session.add(record)
        return record

    async def process_opt_out(
        self,
        *,
        workspace_id: int,
        record_type: str,
        value: str,
        actor_user_id: UUID,
        ip_address: str | None = None,
        global_scope: bool = False,
    ) -> OptOutResult:
        """Process a PII opt-out request.

        1. Upsert a DNC record for the requested value.
        2. Find all matching verified contacts via blind HMAC index.
        3. Purge PII from each contact and append an audit log.
        4. Refund 1,500 micros for each unlocked contact up to the 15% cap.
        5. Invalidate DNC cache.
        """
        if record_type == "phone":
            e164 = normalize_phone_e164(value)
            if not e164:
                raise ValueError(f"Invalid phone format: {value}")
            value_hmac = compute_phone_hmac(e164)
        elif record_type == "email":
            norm_email = normalize_email(value)
            if not norm_email:
                raise ValueError(f"Invalid email format: {value}")
            value_hmac = compute_email_hmac(norm_email)
        else:
            raise ValueError(f"Unsupported opt-out record type: {record_type}")

        dnc_record = await self._ensure_dnc_record(
            workspace_id=workspace_id,
            record_type=record_type,
            value=e164 if record_type == "phone" else norm_email,
            value_hmac=value_hmac,
            reason="Right to be forgotten",
            global_scope=global_scope,
        )

        if record_type == "phone":
            match_clause = VerifiedContact.phone_hmac == value_hmac
        else:
            match_clause = VerifiedContact.email_hmac == value_hmac

        contacts = (
            (
                await self.session.execute(
                    select(VerifiedContact).where(
                        VerifiedContact.workspace_id == workspace_id,
                        match_clause,
                    )
                )
            )
            .scalars()
            .all()
        )

        refundable_slots = await _count_refundable_unlocks_this_cycle(
            self.session, workspace_id
        )

        purged_count = 0
        refunded_micros = 0
        for contact in contacts:
            was_unlocked = bool(contact.is_unlocked)

            if was_unlocked and refundable_slots > 0:
                original_event = await _find_original_unlock_billing_event(
                    self.session, contact.id, workspace_id
                )
                if original_event is not None:
                    await self._refund_credit(contact, original_event, workspace_id)
                    refunded_micros += _REFUND_AMOUNT_MICROS
                    refundable_slots -= 1

            _anonymize_contact(contact)
            _append_opt_out_audit_log(
                contact,
                actor_id=actor_user_id,
                ip_address=ip_address,
                reason="Right to be forgotten",
            )
            purged_count += 1

        if not global_scope:
            dnc_service = DncComplianceService(secret_key=config.SECRET_KEY)
            await dnc_service.invalidate_workspace_cache(workspace_id)
        else:
            dnc_service = DncComplianceService(secret_key=config.SECRET_KEY)
            await dnc_service.invalidate_global_cache()

        return OptOutResult(
            purged_contact_count=purged_count,
            refunded_micros=refunded_micros,
            dnc_record_id=dnc_record.id,
        )
