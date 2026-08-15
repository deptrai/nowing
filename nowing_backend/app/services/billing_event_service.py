"""BillingEvent ledger for non-LLM business events."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import BillingEvent
from app.services import wallet_credit


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
) -> BillingEvent:
    """Core path: check duplicate, write BillingEvent, debit wallet."""
    # Idempotency: look for an existing billing row for this event.
    existing = (
        await session.execute(
            select(BillingEvent).where(
                BillingEvent.event_entity_type == event_entity_type,
                BillingEvent.event_type == event_type,
                BillingEvent.event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
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
            raise ValueError(
                f"duplicate billing event for {event_entity_type} id={event_id}"
            )

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

    if cost_micros > 0 and user_id is not None:
        await wallet_credit.check_balance(session, user_id, cost_micros)
        try:
            await wallet_credit.apply_debit(session, user_id, cost_micros)
        except Exception:
            await session.rollback()
            raise
    else:
        # Zero-cost or ownerless event still creates a BillingEvent row.
        await session.commit()

    return event
