"""Red-phase ATDD unit tests for contact relock / accidental unlock refund.

Covers BillingEventService.record_contact_relock: 60s window, 15% budget,
idempotency, wallet credit, and monthly spent reversal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.billing_event_service import BillingEventService
from app.services.workspace_credit_service import WorkspaceCreditService

pytestmark = [
    pytest.mark.unit,
]


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        if self._value is None:
            raise ValueError("No row found")
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """AsyncSession stand-in with per-query result mapping."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self.query_map: dict[str, Any] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        try:
            compiled = stmt.compile(compile_kwargs={"literal_binds": True})
            text = str(compiled).lower()
        except Exception:
            text = str(stmt).lower()
        for key, value in self.query_map.items():
            if key.lower() in text:
                if isinstance(value, list):
                    return _FakeResult(rows=value)
                return _FakeResult(value=value)
        return _FakeResult()

    async def get(self, _model: type, _ident: Any) -> Any | None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, _obj: Any) -> None:
        pass


def _make_unlock_billing_event(
    contact_id: UUID,
    user_id: UUID,
    created_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        workspace_id=1,
        event_entity_type="verified_contact",
        event_type="contact_unlock",
        event_id=contact_id,
        cost_micros=1500,
        created_at=created_at or datetime.now(UTC),
    )


def _make_relock_billing_event(
    contact_id: UUID,
    user_id: UUID,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        workspace_id=1,
        event_entity_type="verified_contact",
        event_type="contact_relock",
        event_id=contact_id,
        cost_micros=-1500,
        created_at=datetime.now(UTC),
    )


def _patch_wallet_and_spend(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {"credit": [], "refund_spend": []}

    async def _apply_credit(_session: Any, user_id: Any, amount_micros: int) -> int:
        calls["credit"].append({"user_id": user_id, "amount_micros": amount_micros})
        return amount_micros

    async def _refund_member_spend(
        self: WorkspaceCreditService,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
    ) -> dict[str, Any]:
        calls["refund_spend"].append(
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": amount_micros,
            }
        )
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "amount_micros": amount_micros,
            "member_monthly_spent": 0,
        }

    import app.services.wallet_credit as wallet_credit

    monkeypatch.setattr(wallet_credit, "apply_credit", _apply_credit)
    monkeypatch.setattr(
        WorkspaceCreditService, "refund_member_spend", _refund_member_spend
    )
    return calls


@pytest.mark.asyncio
async def test_record_contact_relock_returns_negative_billing_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0: record_contact_relock writes a -1500 micros BillingEvent."""
    calls = _patch_wallet_and_spend(monkeypatch)
    contact_id = uuid4()
    user_id = uuid4()
    original = _make_unlock_billing_event(contact_id, user_id)

    session = _FakeSession()
    session.query_map["contact_unlock"] = [original]
    session.query_map["contact_relock"] = []

    result = await BillingEventService().record_contact_relock(
        session,
        verified_contact_id=contact_id,
        workspace_id=1,
        user_id=user_id,
    )

    assert result.event_type == "contact_relock"
    assert result.cost_micros == -1500
    assert result.user_id == user_id
    assert len(calls["credit"]) == 1
    assert calls["credit"][0]["amount_micros"] == 1500
    assert calls["credit"][0]["user_id"] == user_id
    assert len(calls["refund_spend"]) == 1
    assert calls["refund_spend"][0]["amount_micros"] == 1500


@pytest.mark.asyncio
async def test_record_contact_relock_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0: a second relock for the same contact returns the existing event."""
    _patch_wallet_and_spend(monkeypatch)
    contact_id = uuid4()
    user_id = uuid4()
    original = _make_unlock_billing_event(contact_id, user_id)
    existing_relock = _make_relock_billing_event(contact_id, user_id)

    session = _FakeSession()
    session.query_map["contact_unlock"] = [original]
    session.query_map["contact_relock"] = [existing_relock]

    first = await BillingEventService().record_contact_relock(
        session,
        verified_contact_id=contact_id,
        workspace_id=1,
        user_id=user_id,
    )
    second = await BillingEventService().record_contact_relock(
        session,
        verified_contact_id=contact_id,
        workspace_id=1,
        user_id=user_id,
    )

    assert first is second
    assert first is existing_relock
    assert not session.added


@pytest.mark.asyncio
async def test_record_contact_relock_refuses_expired_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0: relock beyond 60s window is rejected."""
    _patch_wallet_and_spend(monkeypatch)
    contact_id = uuid4()
    user_id = uuid4()
    original = _make_unlock_billing_event(
        contact_id,
        user_id,
        created_at=datetime.now(UTC) - timedelta(seconds=61),
    )

    session = _FakeSession()
    session.query_map["contact_unlock"] = [original]
    session.query_map["contact_relock"] = []

    with pytest.raises((ValueError, RuntimeError)):
        await BillingEventService().record_contact_relock(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )


@pytest.mark.asyncio
async def test_record_contact_relock_refuses_when_no_original_unlock() -> None:
    """P0: relock without a prior contact_unlock BillingEvent is rejected."""
    session = _FakeSession()
    session.query_map["contact_unlock"] = []
    session.query_map["contact_relock"] = []

    with pytest.raises((ValueError, RuntimeError)):
        await BillingEventService().record_contact_relock(
            session,
            verified_contact_id=uuid4(),
            workspace_id=1,
            user_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_record_contact_relock_refuses_when_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0: relock is capped at 15% of unlocked leads per billing cycle."""
    _patch_wallet_and_spend(monkeypatch)
    contact_id = uuid4()
    user_id = uuid4()
    original = _make_unlock_billing_event(contact_id, user_id)

    session = _FakeSession()
    session.query_map["contact_unlock"] = [original]
    # Simulate budget already consumed by 20 prior relocks for 100 unlocked leads.
    session.query_map["contact_relock"] = list(range(20))

    with pytest.raises((ValueError, RuntimeError)):
        await BillingEventService().record_contact_relock(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )
