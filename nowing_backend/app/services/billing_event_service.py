"""BillingEvent ledger for non-LLM business events."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import BillingEvent
from app.services import wallet_credit
from app.services.workspace_credit_service import (
    WorkspaceCreditService,
)


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
            raise ValueError(
                f"no unlock billing event for contact {verified_contact_id}"
            )

        payer_id = original.user_id
        if payer_id is None:
            payer_id = user_id

        # 3. Refund cannot exceed the original unlock cost.
        refund_micros = min(cost_micros, original.cost_micros or cost_micros)

        # 4. Credit the payer wallet and decrement member monthly spent.
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
        workspace_id: int,
        client_id: str | None = None,
        user_id: UUID | None,
        cost_micros: int,
        cost_basis: str = "actual",
    ) -> BillingEvent:
        """Record an outbound sequence send billing event and debit user wallet (Story 24.1 / AD-42).

        Idempotent by sequence_event_id: returns existing BillingEvent on duplicate to be retry-safe with Celery.
        """
        return await _record_business_event(
            session,
            event_entity_type="sequence_event",
            event_type="email_send",
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
        # Debit the wallet first; only persist BillingEvent after a successful debit.
        try:
            await wallet_credit.check_balance(session, user_id, cost_micros)

            credit_svc = WorkspaceCreditService(session=session)
            await credit_svc.record_spend(
                workspace_id=workspace_id,
                user_id=user_id,
                amount_micros=cost_micros,
            )
            await wallet_credit.apply_debit(session, user_id, cost_micros)
        except Exception:
            await session.rollback()
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
    return event
