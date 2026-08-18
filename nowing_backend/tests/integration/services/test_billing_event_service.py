"""Pattern 6 integration tests for BillingEventService (Story 26.5).

These tests run the real BillingEventService against a real Postgres database
through the transactional ``db_session`` fixture. They assert actual SQL
execution, wallet changes, membership monthly_spent updates, and BillingEvent
ledger state.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import BillingEvent, User, Workspace, WorkspaceMembership
from app.services.billing_event_service import BillingEventService

pytestmark = [pytest.mark.integration]

COST_MICROS = 1_500


async def _membership(
    db_session, db_workspace: Workspace, db_user: User
) -> WorkspaceMembership:
    result = await db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == db_workspace.id,
            WorkspaceMembership.user_id == db_user.id,
        )
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_record_contact_unlock_persists_and_debits_wallet_and_spending(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: contact_unlock writes a BillingEvent, debits wallet, records spend."""
    db_user.credit_micros_balance = 5_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    contact_id = uuid4()
    svc = BillingEventService()

    event = await svc.record_contact_unlock(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )

    assert event.event_type == "contact_unlock"
    assert event.event_entity_type == "verified_contact"
    assert event.event_id == contact_id
    assert event.workspace_id == db_workspace.id
    assert event.user_id == db_user.id
    assert event.cost_micros == COST_MICROS

    # Pattern 6: query the persisted row back from the real database.
    await db_session.flush()
    row = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.event_id == contact_id,
                BillingEvent.event_type == "contact_unlock",
            )
        )
    ).scalar_one()
    assert row.cost_micros == COST_MICROS

    user = await db_session.get(User, db_user.id)
    assert user is not None
    assert user.credit_micros_balance == 5_000 - COST_MICROS

    membership = await _membership(db_session, db_workspace, db_user)
    assert membership.monthly_spent_micros == COST_MICROS


@pytest.mark.asyncio
async def test_record_contact_unlock_is_idempotent(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: calling contact_unlock twice for the same contact bills only once."""
    db_user.credit_micros_balance = 5_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    contact_id = uuid4()
    svc = BillingEventService()

    first = await svc.record_contact_unlock(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )
    await db_session.flush()

    second = await svc.record_contact_unlock(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )

    assert second.id == first.id
    assert second.event_type == "contact_unlock"

    events = (
        (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_id == contact_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1

    user = await db_session.get(User, db_user.id)
    assert user is not None
    assert user.credit_micros_balance == 5_000 - COST_MICROS

    membership = await _membership(db_session, db_workspace, db_user)
    assert membership.monthly_spent_micros == COST_MICROS


@pytest.mark.asyncio
async def test_record_contact_unlock_refund_credits_wallet_and_reverses_spend(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: refund finds the original unlock, credits wallet, reverses spend."""
    db_user.credit_micros_balance = 5_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    contact_id = uuid4()
    svc = BillingEventService()

    await svc.record_contact_unlock(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )
    await db_session.flush()

    refund = await svc.record_contact_unlock_refund(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )

    assert refund.event_type == "contact_unlock_refund"
    assert refund.event_entity_type == "verified_contact"
    assert refund.event_id == contact_id
    assert refund.workspace_id == db_workspace.id
    assert refund.user_id == db_user.id
    assert refund.cost_micros == -COST_MICROS

    await db_session.flush()
    events = (
        (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_id == contact_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 2
    assert {e.event_type for e in events} == {"contact_unlock", "contact_unlock_refund"}
    assert sum(e.cost_micros for e in events) == 0

    user = await db_session.get(User, db_user.id)
    assert user is not None
    assert user.credit_micros_balance == 5_000

    membership = await _membership(db_session, db_workspace, db_user)
    assert membership.monthly_spent_micros == 0


@pytest.mark.asyncio
async def test_record_contact_unlock_refund_is_idempotent(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: calling refund twice for the same contact refunds only once."""
    db_user.credit_micros_balance = 5_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    contact_id = uuid4()
    svc = BillingEventService()

    await svc.record_contact_unlock(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )
    await db_session.flush()

    first_refund = await svc.record_contact_unlock_refund(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )
    await db_session.flush()

    second_refund = await svc.record_contact_unlock_refund(
        db_session,
        verified_contact_id=contact_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=COST_MICROS,
    )

    assert second_refund.id == first_refund.id

    refunds = (
        (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_id == contact_id,
                    BillingEvent.event_type == "contact_unlock_refund",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(refunds) == 1

    user = await db_session.get(User, db_user.id)
    assert user is not None
    assert user.credit_micros_balance == 5_000

    membership = await _membership(db_session, db_workspace, db_user)
    assert membership.monthly_spent_micros == 0


@pytest.mark.asyncio
async def test_record_contact_unlock_refund_fails_when_no_original_unlock(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: refund without an original contact_unlock BillingEvent is rejected."""
    db_user.credit_micros_balance = 5_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    contact_id = uuid4()
    svc = BillingEventService()

    with pytest.raises(ValueError, match="no unlock billing event"):
        await svc.record_contact_unlock_refund(
            db_session,
            verified_contact_id=contact_id,
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            cost_micros=COST_MICROS,
        )

    events = (
        (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_id == contact_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert not events

    user = await db_session.get(User, db_user.id)
    assert user is not None
    assert user.credit_micros_balance == 5_000

    membership = await _membership(db_session, db_workspace, db_user)
    assert membership.monthly_spent_micros == 0
