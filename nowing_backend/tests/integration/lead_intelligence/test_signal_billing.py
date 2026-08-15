"""Pattern 6 (SQL) integration tests for Story 21.1 signal billing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import BillingEvent, SignalEvent, User, Workspace
from app.services.billing_event_service import BillingEventService, record_signal_scan

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _make_signal_event(workspace_id: int, **overrides: Any) -> SignalEvent:
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "workspace_id": workspace_id,
        "client_id": None,
        "company_name": "FPT",
        "signal_type": "funding",
        "source_url": "https://example.com/funding",
        "chunk_id": None,
        "confidence": 85.0,
        "detected_at": datetime.now(UTC),
        "processed": False,
    }
    defaults.update(overrides)
    return SignalEvent(**defaults)


async def test_billing_event_insert_and_select(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    seed_billing_event: Any,
) -> None:
    """BillingEvent rows persist with the signal_scan contract fields."""
    signal = _make_signal_event(db_workspace.id)
    db_session.add(signal)
    await db_session.flush()

    event = await seed_billing_event(signal.id, cost_micros=2500)

    result = await db_session.execute(
        select(BillingEvent).where(BillingEvent.workspace_id == db_workspace.id)
    )
    rows = list(result.scalars().all())
    assert len(rows) == 1

    row = rows[0]
    assert row.event_entity_type == "signal_event"
    assert row.event_type == "signal_scan"
    assert row.event_id == signal.id
    assert row.cost_micros == 2500
    assert row.currency == "USD"
    assert row.cost_basis == "estimated"
    assert row.workspace_id == db_workspace.id
    assert row.user_id == db_user.id
    assert row.id == event.id


async def test_record_signal_scan_writes_billing_event_and_debits_wallet(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """record_signal_scan writes a BillingEvent and debits User.credit_micros_balance."""
    from app.config import config

    monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 1000, raising=False)

    signal = _make_signal_event(db_workspace.id)
    db_session.add(signal)
    await db_session.flush()

    db_user.credit_micros_balance = 1_000_000
    await db_session.flush()

    await record_signal_scan(
        db_session,
        signal_event_id=signal.id,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        cost_micros=2500,
    )

    result = await db_session.execute(
        select(BillingEvent).where(BillingEvent.event_id == signal.id)
    )
    row = result.scalar_one()
    assert row.event_entity_type == "signal_event"
    assert row.event_type == "signal_scan"
    assert row.cost_micros == 2500

    updated_user = await db_session.get(User, db_user.id)
    assert updated_user is not None
    assert updated_user.credit_micros_balance == 1_000_000 - 2500


async def test_record_signal_scan_idempotent(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling record_signal_scan twice for the same signal writes one BillingEvent."""
    from app.config import config

    monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 1000, raising=False)

    signal = _make_signal_event(db_workspace.id)
    db_session.add(signal)
    await db_session.flush()

    db_user.credit_micros_balance = 1_000_000
    await db_session.flush()

    await record_signal_scan(
        db_session,
        signal_event_id=signal.id,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        cost_micros=1000,
    )

    with pytest.raises(ValueError, match="duplicate"):
        await record_signal_scan(
            db_session,
            signal_event_id=signal.id,
            workspace_id=db_workspace.id,
            client_id=None,
            user_id=db_user.id,
            cost_micros=1000,
        )

    result = await db_session.execute(
        select(BillingEvent).where(BillingEvent.event_id == signal.id)
    )
    assert len(list(result.scalars().all())) == 1


async def test_billing_event_service_record_scan(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BillingEventService.record_scan writes the ledger row."""
    from app.config import config

    monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 500, raising=False)

    signal = _make_signal_event(db_workspace.id)
    db_session.add(signal)
    await db_session.flush()

    db_user.credit_micros_balance = 1_000_000
    await db_session.flush()

    service = BillingEventService()
    await service.record_scan(
        db_session,
        signal_event_id=signal.id,
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        cost_micros=500,
    )

    result = await db_session.execute(
        select(BillingEvent).where(BillingEvent.event_id == signal.id)
    )
    row = result.scalar_one()
    assert row.event_entity_type == "signal_event"
    assert row.event_type == "signal_scan"
    assert row.cost_micros == 500


async def test_billing_event_respects_partial_unique_index_for_outcome_event(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """Partial unique index on (event_id) WHERE event_entity_type='outcome_event'."""
    event_id = uuid4()

    be1 = BillingEvent(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        event_entity_type="outcome_event",
        event_type="outcome",
        event_id=event_id,
        cost_micros=1000,
    )
    db_session.add(be1)
    await db_session.flush()

    be2 = BillingEvent(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        user_id=db_user.id,
        event_entity_type="outcome_event",
        event_type="outcome",
        event_id=event_id,
        cost_micros=1000,
    )
    db_session.add(be2)

    with pytest.raises(IntegrityError):
        await db_session.flush()
