"""BillingEvent ledger for non-LLM business events."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import BillingEvent
from app.services import wallet_credit
from app.services.workspace_credit_service import (
    SpendCapExceededError,
    WorkspaceCreditService,
)

logger = logging.getLogger(__name__)


class RefundWindowExpiredError(ValueError):
    """Raised when a 24h contact-unlock refund window has expired."""


class RefundBudgetExhaustedError(ValueError):
    """Raised when the 15% auto-refund budget cap is exhausted."""


class RefundAlreadyProcessedError(ValueError):
    """Raised when a contact has already been relocked or refunded."""


class NoOriginalUnlockEventError(ValueError):
    """Raised when the original contact_unlock billing event is missing."""


class RelockWindowExpiredError(ValueError):
    """Raised when the 60s accidental-relock window has expired."""


class RelockBudgetExhaustedError(ValueError):
    """Raised when the 15% accidental-relock budget cap is exhausted."""


# ponytail: in-process lock so concurrent relock requests in the same worker
# (e.g. the integration-test AsyncClient that reuses one db_session) are
# serialized. The DB advisory lock still protects cross-worker/process races.
_RELOCK_LOCK = asyncio.Lock()


class BillingEventService:
    """Write business-event ledger rows and debit the workspace owner."""

    @classmethod
    async def record_scan(
        cls,
        session: AsyncSession,
        *,
        signal_event_id: UUID | None,
        workspace_id: int,
        client_id: str | None,
        user_id: UUID | None,
        cost_micros: int,
    ) -> BillingEvent | None:
        """Record a signal-scan billing event and debit the owner if needed."""
        return await record_signal_scan(
            session,
            signal_event_id=signal_event_id,
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=user_id,
            cost_micros=cost_micros,
        )

    async def record_lead_scoring(
        self,
        session: AsyncSession,
        *,
        lead_score_id: UUID,
        workspace_id: int,
        client_id: str | None,
        user_id: UUID,
        cost_micros: int,
    ) -> BillingEvent:
        """Record a lead-scoring billing event and debit the owner."""
        return await _record_business_event(
            session,
            event_entity_type="lead_score",
            event_type="lead_scoring",
            event_id=lead_score_id,
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=user_id,
            cost_micros=cost_micros,
        )

    async def record_contact_unlock(
        self,
        session: AsyncSession,
        *,
        verified_contact_id: UUID,
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID,
        cost_micros: int = 1_500,
    ) -> BillingEvent:
        """Record a contact-unlock billing event and debit the owner (Story 26.1 / AD-105).

        Uses ``cost_basis="actual"`` and is idempotent by ``verified_contact_id``:
        a duplicate call returns the existing BillingEvent so retries are safe.
        """
        return await _record_business_event(
            session,
            event_entity_type="verified_contact",
            event_type="contact_unlock",
            event_id=verified_contact_id,
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=user_id,
            cost_micros=cost_micros,
            cost_basis="actual",
            return_existing=True,
        )

    async def record_contact_unlock_refund(
        self,
        session: AsyncSession,
        *,
        verified_contact_id: UUID,
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID,
        cost_micros: int = 1_500,
    ) -> BillingEvent:
        """Record a contact-unlock refund and credit the payer wallet (Story 26.4).

        Idempotent: returns an existing refund BillingEvent if one already exists.
        Refunds are capped at the original unlock cost.
        """
        # ponytail: serialize all refund attempts for the same contact. The first
        # SELECT FOR UPDATE cannot lock a refund row that does not exist yet, so
        # concurrent first refunds would both pass the check and double-credit.
        await _acquire_billing_lock(
            session, "verified_contact", "contact_unlock_refund", verified_contact_id
        )

        # 1. Idempotency: existing refund row for this contact (lock for update).
        existing_refund = (
            await session.execute(
                select(BillingEvent)
                .where(
                    BillingEvent.event_entity_type == "verified_contact",
                    BillingEvent.event_type == "contact_unlock_refund",
                    BillingEvent.event_id == verified_contact_id,
                    BillingEvent.workspace_id == workspace_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if getattr(existing_refund, "event_type", None) == "contact_unlock_refund":
            return existing_refund

        # 2. Find the original unlock billing event to identify the payer.
        original = (
            await session.execute(
                select(BillingEvent)
                .where(
                    BillingEvent.event_entity_type == "verified_contact",
                    BillingEvent.event_type == "contact_unlock",
                    BillingEvent.event_id == verified_contact_id,
                    BillingEvent.workspace_id == workspace_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if getattr(original, "event_type", None) != "contact_unlock":
            raise NoOriginalUnlockEventError(
                f"no unlock billing event for contact {verified_contact_id}"
            )

        payer_id = original.user_id
        if payer_id is None:
            payer_id = user_id

        # 3. Refund cannot exceed the original unlock cost.
        refund_micros = min(cost_micros, original.cost_micros or cost_micros)

        # 4. Credit the payer wallet and decrement member monthly spent.
        # NOTE: apply_credit commits the session, so the BillingEvent is added
        # afterwards to keep it in the caller's transaction. OptOutService relies
        # on session.new/add to detect a newly created refund event.
        await wallet_credit.apply_credit(session, payer_id, refund_micros)
        credit_svc = WorkspaceCreditService(session=session)
        await credit_svc.refund_member_spend(
            workspace_id=workspace_id,
            user_id=payer_id,
            amount_micros=refund_micros,
        )

        # 5. Persist the refund billing event (negative cost).
        event = BillingEvent(
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=payer_id,
            event_entity_type="verified_contact",
            event_type="contact_unlock_refund",
            event_id=verified_contact_id,
            cost_micros=-refund_micros,
            currency="USD",
            cost_basis="actual",
        )
        session.add(event)
        return event

    async def record_contact_relock(
        self,
        session: AsyncSession,
        *,
        verified_contact_id: UUID,
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID,
        cost_micros: int = 1_500,
        relock_window_seconds: int = 60,
    ) -> BillingEvent:
        """Record an accidental contact relock (60s window) refund.

        Refunds the original payer, decrements member monthly spend, and writes a
        negative ``contact_relock`` BillingEvent. Idempotent: a duplicate call
        returns the existing relock row. Enforces a 60-second relock window and a
        15% accidental-relock budget per billing cycle (separate from opt-out cap).
        """
        # ponytail: in-process serialization. Combined with the DB advisory lock
        # below this makes the read-check-write for relocks safe even when one
        # AsyncSession is reused by concurrent test callers.
        async with _RELOCK_LOCK:
            await _acquire_billing_lock(
                session, "verified_contact", "contact_relock", verified_contact_id
            )

            # 1. Idempotency: an existing relock row for this contact.
            existing_rows = await _list_billing_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_relock",
                event_id=verified_contact_id,
                workspace_id=workspace_id,
            )
            if existing_rows:
                return existing_rows[0]

            # 2. A refund already processed prevents a relock.
            existing_refunds = await _list_billing_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_unlock_refund",
                event_id=verified_contact_id,
                workspace_id=workspace_id,
            )
            if existing_refunds:
                raise RefundAlreadyProcessedError(
                    "refund already processed for this contact"
                )

            # 2. Original unlock event must exist and be within the relock window.
            original_rows = await _list_billing_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_unlock",
                event_id=verified_contact_id,
                workspace_id=workspace_id,
            )
            original = original_rows[0] if original_rows else None
            if (
                original is None
                or getattr(original, "event_type", None) != "contact_unlock"
            ):
                raise NoOriginalUnlockEventError(
                    f"no unlock billing event for contact {verified_contact_id}"
                )

            created_at = getattr(original, "created_at", None)
            if created_at is None:
                raise NoOriginalUnlockEventError(
                    "original unlock event has no timestamp"
                )
            now = datetime.now(UTC)
            if now - created_at > timedelta(seconds=relock_window_seconds):
                raise RelockWindowExpiredError("relock window expired")

            # 3. Accidental-relock budget: 15% of unlocked leads this billing cycle.
            cycle_start, cycle_end = _billing_cycle_bounds(now)
            relock_count = await _count_workspace_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_relock",
                workspace_id=workspace_id,
                since=cycle_start,
                until=cycle_end,
            )
            unlock_count = await _count_workspace_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_unlock",
                workspace_id=workspace_id,
                since=cycle_start,
                until=cycle_end,
            )
            if unlock_count > 0:
                cap = math.ceil(unlock_count * 0.15)
                if relock_count >= cap:
                    raise RelockBudgetExhaustedError("relock budget exhausted")

            # 4. Build the relock billing event before committing.
            payer_id = original.user_id or user_id
            original_cost = original.cost_micros
            if original_cost is None:
                original_cost = cost_micros
            refund_micros = min(cost_micros, max(0, original_cost))

            event = BillingEvent(
                workspace_id=workspace_id,
                client_id=client_id,
                user_id=payer_id,
                event_entity_type="verified_contact",
                event_type="contact_relock",
                event_id=verified_contact_id,
                cost_micros=-refund_micros,
                currency="USD",
                cost_basis="actual",
            )
            session.add(event)

            # 5. Credit the original payer and refund their monthly spend.
            credit_svc = WorkspaceCreditService(session=session)
            await credit_svc.refund_member_spend(
                workspace_id=workspace_id,
                user_id=payer_id,
                amount_micros=refund_micros,
            )
            await wallet_credit.apply_credit(session, payer_id, refund_micros)
            return event

    async def record_contact_unlock_refund_24h(
        self,
        session: AsyncSession,
        *,
        verified_contact_id: UUID,
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID,
        cost_micros: int = 1_500,
        refund_window_hours: int = 24,
    ) -> BillingEvent:
        """Record a 24h auto-refund for an invalid contact (Telegram 1-click refund).

        Refunds the original payer, decrements member monthly spend, writes a
        negative ``contact_unlock_refund`` BillingEvent, and updates contact state.
        Enforces a 24-hour SLA window and a 15% budget cap per billing cycle.
        """
        async with _RELOCK_LOCK:
            await _acquire_billing_lock(
                session,
                "verified_contact",
                "contact_unlock_refund",
                verified_contact_id,
            )

            # 1. Idempotency: check for existing refund or relock row (prevent double refund)
            existing_refunds = await _list_billing_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_unlock_refund",
                event_id=verified_contact_id,
                workspace_id=workspace_id,
            )
            if existing_refunds:
                return existing_refunds[0]

            existing_relocks = await _list_billing_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_relock",
                event_id=verified_contact_id,
                workspace_id=workspace_id,
            )
            if existing_relocks:
                # A relock already refunded this contact. Do not conflate the ledger
                # by returning a contact_relock event as a contact_unlock_refund.
                raise RefundAlreadyProcessedError(
                    "contact already relocked; refund already processed"
                )

            # 2. Original unlock event must exist and be within the 24h window
            original_rows = await _list_billing_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_unlock",
                event_id=verified_contact_id,
                workspace_id=workspace_id,
            )
            original = original_rows[0] if original_rows else None
            if (
                original is None
                or getattr(original, "event_type", None) != "contact_unlock"
            ):
                raise NoOriginalUnlockEventError(
                    f"no original unlock billing event found for contact {verified_contact_id}"
                )

            created_at = getattr(original, "created_at", None)
            if created_at is None:
                raise NoOriginalUnlockEventError(
                    "original unlock event has no timestamp"
                )
            now = datetime.now(UTC)
            if now - created_at > timedelta(hours=refund_window_hours):
                raise RefundWindowExpiredError("24h refund window expired")

            # 3. 15% auto-refund cap across the current and original-unlock billing cycles.
            current_cycle_start, current_cycle_end = _billing_cycle_bounds(now)
            original_cycle_start, original_cycle_end = _billing_cycle_bounds(created_at)

            refund_count = await _count_workspace_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_unlock_refund",
                workspace_id=workspace_id,
                since=current_cycle_start,
                until=current_cycle_end,
            )
            unlock_count = await _count_workspace_events(
                session,
                event_entity_type="verified_contact",
                event_type="contact_unlock",
                workspace_id=workspace_id,
                since=current_cycle_start,
                until=current_cycle_end,
            )

            if (original_cycle_start, original_cycle_end) != (
                current_cycle_start,
                current_cycle_end,
            ):
                refund_count += await _count_workspace_events(
                    session,
                    event_entity_type="verified_contact",
                    event_type="contact_unlock_refund",
                    workspace_id=workspace_id,
                    since=original_cycle_start,
                    until=original_cycle_end,
                )
                unlock_count += await _count_workspace_events(
                    session,
                    event_entity_type="verified_contact",
                    event_type="contact_unlock",
                    workspace_id=workspace_id,
                    since=original_cycle_start,
                    until=original_cycle_end,
                )

            cap_pct = float(getattr(config, "DSH_TELEGRAM_REFUND_CAP_PCT", 0.15))
            cap_pct = max(0.0, min(cap_pct, 1.0))
            cap = math.ceil(unlock_count * cap_pct)
            if refund_count >= cap:
                raise RefundBudgetExhaustedError(
                    "auto-refund budget cap exhausted for this billing cycle"
                )

            # 4. Credit original payer and refund monthly spend (after persisting event).
            payer_id = original.user_id or user_id
            original_cost = original.cost_micros
            if original_cost is None:
                original_cost = cost_micros
            refund_micros = min(cost_micros, max(0, original_cost))

            # 5. Mark contact as invalid and audit.
            await self._mark_contact_invalid_for_refund(
                session,
                verified_contact_id=verified_contact_id,
                user_id=user_id,
                workspace_id=workspace_id,
                now=now,
            )

            # 6. Persist negative BillingEvent.
            event = BillingEvent(
                workspace_id=workspace_id,
                client_id=client_id,
                user_id=payer_id,
                event_entity_type="verified_contact",
                event_type="contact_unlock_refund",
                event_id=verified_contact_id,
                cost_micros=-refund_micros,
                currency="USD",
                cost_basis="actual",
            )
            session.add(event)

            credit_svc = WorkspaceCreditService(session=session)
            await credit_svc.refund_member_spend(
                workspace_id=workspace_id,
                user_id=payer_id,
                amount_micros=refund_micros,
            )
            await wallet_credit.apply_credit(session, payer_id, refund_micros)
            return event

    @staticmethod
    async def _mark_contact_invalid_for_refund(
        session: AsyncSession,
        *,
        verified_contact_id: UUID,
        user_id: UUID,
        workspace_id: int,
        now: datetime,
    ) -> None:
        """Mark a VerifiedContact as invalid and append a refund audit log.

        Safe for fake test sessions that do not implement ``session.get``.
        """
        session_get = getattr(session, "get", None)
        if session_get is None:
            return

        from app.db import VerifiedContact

        contact = await session_get(VerifiedContact, verified_contact_id)
        if contact is None:
            return

        contact.is_valid = False
        contact.invalid_reason = "telegram_refund"
        contact.verification_status = "invalid"
        contact.refunded_at = now
        existing_logs = list(contact.pii_access_audit_logs or [])
        contact.pii_access_audit_logs = [
            *existing_logs,
            {
                "user_id": str(user_id),
                "workspace_id": workspace_id,
                "lead_id": str(contact.lead_id) if contact.lead_id else None,
                "contact_id": str(verified_contact_id),
                "access_type": "refund",
                "timestamp": now.isoformat(),
                "reason": "invalid_number",
            },
        ]

    async def record_contact_enrichment(
        self,
        session: AsyncSession,
        *,
        enrichment_request_id: UUID,
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID,
        cost_micros: int,
    ) -> BillingEvent:
        """Record a contact-enrichment billing event and debit the owner.

        Uses ``cost_basis="actual"``: enrichment cost is only known after the
        provider waterfall has returned the verified contacts (Story 21.3,
        Task 8.1). Idempotent: a duplicate call for the same request id raises
        ValueError.
        """
        return await _record_business_event(
            session,
            event_entity_type="enrichment_request",
            event_type="contact_enrichment",
            event_id=enrichment_request_id,
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=user_id,
            cost_micros=cost_micros,
            cost_basis="actual",
        )

    async def record_sequence_send(
        self,
        session: AsyncSession,
        *,
        sequence_event_id: UUID,
        event_type: str = "email_send",
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID | None,
        cost_micros: int,
        cost_basis: str = "actual",
    ) -> BillingEvent:
        """Record an outbound sequence send billing event and debit user wallet (Story 24.1 / AD-42 / AD-48).

        Idempotent by sequence_event_id: returns existing BillingEvent on duplicate to be retry-safe with Celery.
        """
        return await _record_business_event(
            session,
            event_entity_type="sequence_event",
            event_type=event_type,
            event_id=sequence_event_id,
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=user_id,
            cost_micros=cost_micros,
            cost_basis=cost_basis,
            return_existing=True,
        )

    async def record_outcome_meeting_booked(
        self,
        session: AsyncSession,
        *,
        outcome_event_id: UUID,
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID | None,
        cost_micros: int,
        cost_basis: str = "actual",
    ) -> BillingEvent:
        """Record an outcome-based meeting booked billing event (Story 24.1 / AD-42 / AD-48)."""
        return await _record_business_event(
            session,
            event_entity_type="outcome_event",
            event_type="outcome_meeting_booked",
            event_id=outcome_event_id,
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=user_id,
            cost_micros=cost_micros,
            cost_basis=cost_basis,
            return_existing=True,
        )


async def record_signal_scan(
    session: AsyncSession,
    *,
    signal_event_id: UUID | None,
    workspace_id: int,
    client_id: str | None,
    user_id: UUID | None,
    cost_micros: int,
) -> BillingEvent | None:
    """Create a BillingEvent for a signal scan and debit the wallet.

    Idempotent: calling twice for the same signal_event_id raises ValueError.
    """
    if signal_event_id is None:
        return None
    if cost_micros < 0:
        raise ValueError("cost_micros must not be negative")

    return await _record_business_event(
        session,
        event_entity_type="signal_event",
        event_type="signal_scan",
        event_id=signal_event_id,
        workspace_id=workspace_id,
        client_id=client_id,
        user_id=user_id,
        cost_micros=cost_micros,
    )


def _billing_lock_key(entity_type: str, event_type: str, event_id: UUID) -> int:
    """Derive a 63-bit Postgres advisory lock key from a billing event identity.

    ponytail: advisory locks are global and 64-bit signed; we hash the identity
    and mask to the positive range. Collision is unlikely (MD5-64) but possible;
    a duplicate BillingEvent would then serialize unnecessarily rather than
    double-bill. Add a unique index on (entity, type, event_id, workspace_id)
    if this ever becomes a bottleneck.
    """
    key_str = f"{entity_type}:{event_type}:{event_id!s}".encode()
    return int(hashlib.md5(key_str).hexdigest()[:16], 16) & 0x7FFFFFFFFFFFFFFF


async def _acquire_billing_lock(
    session: AsyncSession,
    entity_type: str,
    event_type: str,
    event_id: UUID,
) -> None:
    """Acquire a transaction-scoped advisory lock for the billing identity."""
    key = _billing_lock_key(entity_type, event_type, event_id)
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _billing_cycle_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Return (start, end) of the current monthly billing cycle in UTC."""
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return start, end


async def _list_billing_events(
    session: AsyncSession,
    *,
    event_entity_type: str,
    event_type: str,
    event_id: UUID,
    workspace_id: int,
) -> list[BillingEvent]:
    """Return billing events matching the identity, ordered by recency."""
    result = await session.execute(
        select(BillingEvent)
        .where(
            BillingEvent.event_entity_type == event_entity_type,
            BillingEvent.event_type == event_type,
            BillingEvent.event_id == event_id,
            BillingEvent.workspace_id == workspace_id,
        )
        .order_by(BillingEvent.created_at.desc())
    )
    rows = list(result.scalars().all())
    # ponytail: in-memory / FakeAsyncSession stand-ins may return rows that do
    # not match the WHERE clause, so re-apply the identity filters in Python.
    return [
        row
        for row in rows
        if (
            getattr(row, "event_entity_type", None) == event_entity_type
            and getattr(row, "event_type", None) == event_type
            and getattr(row, "event_id", None) == event_id
            and getattr(row, "workspace_id", None) == workspace_id
        )
    ]


async def _count_workspace_events(
    session: AsyncSession,
    *,
    event_entity_type: str,
    event_type: str,
    workspace_id: int,
    since: datetime,
    until: datetime,
) -> int:
    """Count billing events of a given type in a workspace and time range."""
    result = await session.execute(
        select(BillingEvent).where(
            BillingEvent.event_entity_type == event_entity_type,
            BillingEvent.event_type == event_type,
            BillingEvent.workspace_id == workspace_id,
            BillingEvent.created_at >= since,
            BillingEvent.created_at < until,
        )
    )
    rows = list(result.scalars().all())
    # ponytail: count in Python so FakeAsyncSession tests can return arbitrary
    # row stand-ins without needing a scalar count(). Production DB rows are
    # cheap here because accidental-relock volume is low per workspace.
    return len(rows)


async def _record_business_event(
    session: AsyncSession,
    *,
    event_entity_type: str,
    event_type: str,
    event_id: UUID,
    workspace_id: int,
    client_id: str | None,
    user_id: UUID | None,
    cost_micros: int,
    cost_basis: str = "estimated",
    return_existing: bool = False,
) -> BillingEvent:
    """Core path: check duplicate, write BillingEvent, debit wallet."""
    # Serialize concurrent billing for the same logical event. FOR UPDATE cannot
    # lock a row that does not exist yet, so two first-time calls can race and
    # both insert a BillingEvent.
    await _acquire_billing_lock(session, event_entity_type, event_type, event_id)

    # Idempotency: look for an existing billing row for this event (lock for update).
    existing = (
        await session.execute(
            select(BillingEvent)
            .where(
                BillingEvent.event_entity_type == event_entity_type,
                BillingEvent.event_type == event_type,
                BillingEvent.event_id == event_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is not None:
        if return_existing:
            return existing
        raise ValueError(
            f"duplicate billing event for {event_entity_type} id={event_id}"
        )

    # Also guard against a second call in the same uncommitted session.
    pending = getattr(session, "new", None) or getattr(session, "added", []) or []
    for obj in pending:
        if (
            type(obj).__name__ == "BillingEvent"
            and obj.event_entity_type == event_entity_type
            and obj.event_type == event_type
            and obj.event_id == event_id
        ):
            if return_existing:
                return obj
            raise ValueError(
                f"duplicate billing event for {event_entity_type} id={event_id}"
            )

    if cost_micros > 0 and user_id is not None:
        # Check balance, tentatively reserve the member monthly spend, then debit.
        await wallet_credit.check_balance(session, user_id, cost_micros)

        credit_svc = WorkspaceCreditService(session=session)
        try:
            await credit_svc.record_spend(
                workspace_id=workspace_id,
                user_id=user_id,
                amount_micros=cost_micros,
            )
        except SpendCapExceededError as exc:
            raise wallet_credit.InsufficientCreditsError(
                message=(
                    f"Member {exc.user_id} exceeded monthly spend cap of {exc.cap_micros} micros. "
                    f"Current spent: {exc.current_spent}, requested: {exc.requested}."
                ),
                balance_micros=max(0, exc.cap_micros - exc.current_spent),
                required_micros=exc.requested,
            ) from exc
        try:
            await wallet_credit.apply_debit(session, user_id, cost_micros)
        except Exception:
            # Undo the monthly-spent increment if the wallet debit failed.
            await credit_svc.refund_member_spend(
                workspace_id=workspace_id,
                user_id=user_id,
                amount_micros=cost_micros,
            )
            raise

    event = BillingEvent(
        workspace_id=workspace_id,
        client_id=client_id,
        user_id=user_id,
        event_entity_type=event_entity_type,
        event_type=event_type,
        event_id=event_id,
        cost_micros=cost_micros,
        currency="USD",
        cost_basis=cost_basis,
    )
    session.add(event)

    # ponytail: apply_debit above already commits for positive-cost events. For
    # zero-cost or ownerless events the session still needs a commit so the
    # BillingEvent (and any caller-staged rows) are persisted.
    if cost_micros <= 0 or user_id is None:
        await session.commit()

    return event
