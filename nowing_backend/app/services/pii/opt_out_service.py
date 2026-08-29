"""PII opt-out / Right-to-be-Forgotten service (Story 26.4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    BillingEvent,
    GlobalDncRecord,
    VerifiedContact,
    Workspace,
    WorkspaceDncRecord,
)
from app.lead_intelligence.dnc.normalizer import (
    compute_email_hmac,
    compute_phone_hmac,
    normalize_email,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.services.billing_event_service import BillingEventService

logger = logging.getLogger(__name__)

_REFUND_AMOUNT_MICROS = 1_500


class OptOutValidationError(ValueError):
    """Raised when the opt-out request is malformed or unsupported."""


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
    contact.value_hmac = None
    contact.is_unlocked = False
    contact.is_valid = False
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
            "user_id": str(actor_id),
            "actor_id": str(actor_id),
            "workspace_id": contact.workspace_id,
            "lead_id": str(contact.lead_id),
            "contact_id": str(contact.id),
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
        select(BillingEvent)
        .where(
            BillingEvent.workspace_id == workspace_id,
            BillingEvent.event_entity_type == "verified_contact",
            BillingEvent.event_type == "contact_unlock",
            BillingEvent.event_id == verified_contact_id,
        )
        .with_for_update()
    )
    event = result.scalar_one_or_none()
    if event is None:
        return None
    return event


async def _count_refundable_unlocks_this_cycle(
    session: AsyncSession,
    workspace_id: int,
    cost_micros: int = _REFUND_AMOUNT_MICROS,
) -> int:
    """Remaining contact-unlock refund slots for this workspace in the current cycle.

    Cap = 15% of total `contact_unlock` BillingEvents in the current calendar month.
    At least one slot is allowed when there is at least one unlock, and zero when
    there are none, to avoid refunding contacts that were never unlocked.
    """
    if cost_micros <= 0:
        return 0

    now = datetime.now(UTC)
    cycle_start = datetime(now.year, now.month, 1, tzinfo=UTC)

    total_unlocked = (
        await session.execute(
            select(func.count(BillingEvent.id)).where(
                BillingEvent.workspace_id == workspace_id,
                BillingEvent.event_entity_type == "verified_contact",
                BillingEvent.event_type == "contact_unlock",
                BillingEvent.created_at >= cycle_start,
            )
        )
    ).scalar_one_or_none() or 0

    if not total_unlocked:
        return 0

    allowed = max(1, int(total_unlocked * 0.15))

    already_refunded = (
        await session.execute(
            select(func.count(BillingEvent.id)).where(
                BillingEvent.workspace_id == workspace_id,
                BillingEvent.event_entity_type == "verified_contact",
                BillingEvent.event_type == "contact_unlock_refund",
                BillingEvent.created_at >= cycle_start,
            )
        )
    ).scalar_one_or_none() or 0

    return max(0, allowed - already_refunded)


class OptOutService:
    """Process PII opt-out requests per PDPD Decree 13/2023/ND-CP."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _is_new_billing_event(session: AsyncSession, event: BillingEvent) -> bool:
        """Heuristic to detect whether a returned BillingEvent was just created."""
        if event is None:
            return False
        if hasattr(session, "new") and session.new and event in session.new:
            return True
        return event in getattr(session, "added", [])

    async def _refund_credit(
        self,
        contact: VerifiedContact,
        original_event: BillingEvent,
        workspace_id: int,
        actor_user_id: UUID,
    ) -> int:
        """Refund one contact unlock and return refunded micros.

        Uses BillingEventService.record_contact_unlock_refund for idempotency,
        wallet credit, member monthly-spent refund, and ledger writing.
        """
        payer_id = original_event.user_id
        if payer_id is None:
            workspace = await self.session.get(Workspace, workspace_id)
            payer_id = getattr(workspace, "user_id", None) or actor_user_id

        refund_amount = min(
            _REFUND_AMOUNT_MICROS,
            original_event.cost_micros or _REFUND_AMOUNT_MICROS,
        )

        event = await BillingEventService().record_contact_unlock_refund(
            self.session,
            verified_contact_id=contact.id,
            workspace_id=workspace_id,
            client_id=None,
            user_id=payer_id,
            cost_micros=refund_amount,
        )

        if not self._is_new_billing_event(self.session, event):
            return 0

        contact.refunded_at = datetime.now(UTC)
        return abs(event.cost_micros)

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
        reason = reason or "Right to be forgotten"
        if global_scope:
            record = GlobalDncRecord(
                id=uuid4(),
                record_type=record_type,
                value=value,
                value_hmac=value_hmac,
                reason=reason,
                source="opt_out",
            )
            self.session.add(record)
            return record

        existing = (
            await self.session.execute(
                select(WorkspaceDncRecord)
                .where(
                    WorkspaceDncRecord.workspace_id == workspace_id,
                    WorkspaceDncRecord.record_type == record_type,
                    WorkspaceDncRecord.value_hmac == value_hmac,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.reason = reason
            existing.source = "opt_out"
            return existing

        record = WorkspaceDncRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            record_type=record_type,
            value=value,
            value_hmac=value_hmac,
            reason=reason,
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
        reason: str | None = None,
    ) -> OptOutResult:
        """Process a PII opt-out request.

        1. Upsert a DNC record for the requested value.
        2. Find all matching verified contacts via blind HMAC index.
        3. Purge PII from each contact and append an audit log.
        4. Refund the original unlock cost for each unlocked contact up to the 15% cap.
        5. Invalidate DNC cache.
        """
        # Serialize per-workspace opt-outs to prevent race over-refunds and DNC dupes.
        await self.session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )

        if record_type == "phone":
            e164 = normalize_phone_e164(value)
            if not e164:
                raise OptOutValidationError(f"Invalid phone format: {value}")
            value_hmac = compute_phone_hmac(e164)
            normalized_value = e164
        elif record_type == "email":
            norm_email = normalize_email(value)
            if not norm_email:
                raise OptOutValidationError(f"Invalid email format: {value}")
            value_hmac = compute_email_hmac(norm_email)
            normalized_value = norm_email
        else:
            raise OptOutValidationError(
                f"Unsupported opt-out record type: {record_type}"
            )

        dnc_record = await self._ensure_dnc_record(
            workspace_id=workspace_id,
            record_type=record_type,
            value=normalized_value,
            value_hmac=value_hmac,
            reason=reason,
            global_scope=global_scope,
        )

        if record_type == "phone":
            match_clause = VerifiedContact.phone_hmac == value_hmac
        else:
            match_clause = VerifiedContact.email_hmac == value_hmac

        contacts = (
            (
                await self.session.execute(
                    select(VerifiedContact)
                    .where(
                        VerifiedContact.workspace_id == workspace_id,
                        match_clause,
                    )
                    .with_for_update()
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
                    refund = await self._refund_credit(
                        contact,
                        original_event,
                        workspace_id,
                        actor_user_id,
                    )
                    if refund > 0:
                        refunded_micros += refund
                        refundable_slots -= 1

            _anonymize_contact(contact)
            _append_opt_out_audit_log(
                contact,
                actor_id=actor_user_id,
                ip_address=ip_address,
                reason=reason,
            )
            purged_count += 1

        dnc_service = DncComplianceService(secret_key=config.SECRET_KEY)
        try:
            if global_scope:
                await dnc_service.invalidate_global_cache()
            else:
                await dnc_service.invalidate_workspace_cache(workspace_id)
        except Exception as exc:
            logger.warning("DNC cache invalidation failed for opt-out: %s", exc)

        return OptOutResult(
            purged_contact_count=purged_count,
            refunded_micros=refunded_micros,
            dnc_record_id=dnc_record.id,
        )
