"""Red-phase ATDD unit tests for Story 26.1 contact unlock billing.

Tests focus on AC-6: BillingEventService.record_contact_unlock, wallet debit,
spend cap, idempotency, audit log.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import Workspace, get_async_session
from app.rate_limiter import limiter
from app.services.billing_event_service import BillingEventService
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.workspace_credit_service import (
    SpendCapExceededError,
    WorkspaceCreditService,
)

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """AsyncSession stand-in that records staged rows and transaction state."""

    def __init__(self, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any, _params: Any | None = None) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

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


def _patch_wallet(
    monkeypatch: pytest.MonkeyPatch,
    *,
    balance_micros: int = 1_000_000,
    spend_raise: Exception | None = None,
    check_raise: Exception | None = None,
) -> dict[str, Any]:
    """Replace wallet primitives with spies and return a call log."""

    calls: dict[str, Any] = {"check": [], "debit": [], "spend": []}

    async def _check_balance(_session: Any, user_id: Any, required_micros: int) -> None:
        calls["check"].append({"user_id": user_id, "required_micros": required_micros})
        if check_raise is not None:
            raise check_raise
        if required_micros > balance_micros:
            raise InsufficientCreditsError(
                message="This run would exceed your available credit.",
                balance_micros=balance_micros,
                required_micros=required_micros,
            )

    async def _apply_debit(_session: Any, user_id: Any, cost_micros: int) -> int:
        calls["debit"].append({"user_id": user_id, "cost_micros": cost_micros})
        return balance_micros - cost_micros

    async def _record_spend(
        self: WorkspaceCreditService,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
        description: str = "",
    ) -> dict[str, Any]:
        calls["spend"].append(
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": amount_micros,
                "description": description,
            }
        )
        if spend_raise is not None:
            raise spend_raise
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "amount_micros": amount_micros,
            "member_monthly_spent": 0,
            "member_monthly_spend_cap": None,
        }

    monkeypatch.setattr(
        "app.services.wallet_credit.check_balance",
        _check_balance,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.wallet_credit.apply_debit",
        _apply_debit,
        raising=False,
    )
    monkeypatch.setattr(
        WorkspaceCreditService,
        "record_spend",
        _record_spend,
        raising=False,
    )
    return calls


@pytest.fixture
def unlock_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Any, Any]:
    """Test client for the contact unlock route with a fake contact."""
    import app.routes.lead_batch_routes as rmod

    monkeypatch.setattr(
        rmod.BillingEventService,
        "record_contact_unlock",
        AsyncMock(return_value=SimpleNamespace(id=uuid4())),
    )
    monkeypatch.setattr(rmod, "check_permission", AsyncMock(return_value=None))

    user = SimpleNamespace(id=uuid4(), is_active=True)
    contact = SimpleNamespace(
        id=uuid4(),
        lead_id=uuid4(),
        workspace_id=1,
        is_unlocked=False,
        is_valid=True,
        consent_status="legitimate_interest",
        phone=None,
        email=None,
        name=None,
        title=None,
        pii_access_audit_logs=[],
    )

    class _RouteSession:
        def __init__(self) -> None:
            self.flushed = False

        async def get(self, model: type, ident: Any) -> Any | None:
            if model is Workspace:
                return SimpleNamespace(id=ident)
            return None

        async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
            if "verified_contacts" in str(stmt).lower():
                return _FakeResult(value=contact)
            return _FakeResult()

        async def flush(self) -> None:
            self.flushed = True

        async def commit(self) -> None:
            pass

        async def refresh(self, _obj: Any) -> None:
            pass

    async def _fake_session():
        yield _RouteSession()

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(rmod.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[rmod.get_auth_context] = lambda: AuthContext.session(user)

    return TestClient(app), contact, user


class TestContactUnlockBilling:
    """AC-6: POST .../contacts/:contact_id/unlock"""

    @pytest.mark.asyncio
    async def test_record_contact_unlock_debits_1500_micros(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should call BillingEventService.record_contact_unlock and debit 1500 micros."""
        calls = _patch_wallet(monkeypatch)
        session = _FakeSession()
        contact_id = uuid4()
        user_id = uuid4()

        result = await BillingEventService().record_contact_unlock(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )

        assert result.cost_micros == 1500
        assert len(calls["check"]) == 1
        assert calls["check"][0]["required_micros"] == 1500
        assert calls["check"][0]["user_id"] == user_id
        assert len(calls["debit"]) == 1
        assert calls["debit"][0]["cost_micros"] == 1500
        assert len(calls["spend"]) == 1
        assert calls["spend"][0]["amount_micros"] == 1500

    @pytest.mark.asyncio
    async def test_record_contact_unlock_writes_billing_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should write BillingEvent with event_type='contact_unlock' and cost_basis='actual'."""
        _patch_wallet(monkeypatch)
        session = _FakeSession()
        contact_id = uuid4()
        user_id = uuid4()

        await BillingEventService().record_contact_unlock(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )

        assert len(session.added) == 1
        event = session.added[0]
        assert type(event).__name__ == "BillingEvent"
        assert event.event_entity_type == "verified_contact"
        assert event.event_type == "contact_unlock"
        assert event.event_id == contact_id
        assert event.workspace_id == 1
        assert event.user_id == user_id
        assert event.cost_micros == 1500
        assert event.currency == "USD"
        assert event.cost_basis == "actual"

    @pytest.mark.asyncio
    async def test_record_contact_unlock_enforces_spend_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should raise SpendCapExceededError when per-seat cap is hit."""
        spend_error = SpendCapExceededError(
            user_id=uuid4(),
            cap_micros=1000,
            current_spent=0,
            requested=1500,
        )
        calls = _patch_wallet(monkeypatch, spend_raise=spend_error)
        session = _FakeSession()

        with pytest.raises(InsufficientCreditsError):
            await BillingEventService().record_contact_unlock(
                session,
                verified_contact_id=uuid4(),
                workspace_id=1,
                user_id=uuid4(),
            )

        assert not session.added
        assert len(calls["check"]) == 1
        assert len(calls["spend"]) == 1
        assert not calls["debit"]

    @pytest.mark.asyncio
    async def test_record_contact_unlock_is_idempotent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should return existing BillingEvent on second call for same contact."""
        calls = _patch_wallet(monkeypatch)
        session = _FakeSession()
        contact_id = uuid4()
        user_id = uuid4()
        service = BillingEventService()

        first = await service.record_contact_unlock(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )
        second = await service.record_contact_unlock(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )

        assert first is second
        assert first is session.added[0]
        assert len(session.added) == 1
        assert len(calls["check"]) == 1
        assert len(calls["debit"]) == 1
        assert len(calls["spend"]) == 1

    @pytest.mark.asyncio
    async def test_record_contact_unlock_insufficient_credits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should raise InsufficientCreditsError and not write a BillingEvent."""
        calls = _patch_wallet(monkeypatch, balance_micros=0)
        session = _FakeSession()

        with pytest.raises(InsufficientCreditsError):
            await BillingEventService().record_contact_unlock(
                session,
                verified_contact_id=uuid4(),
                workspace_id=1,
                user_id=uuid4(),
            )

        assert not session.added
        assert len(calls["check"]) == 1
        assert not calls["debit"]
        assert not calls["spend"]

    def test_record_contact_unlock_appends_audit_log(
        self,
        unlock_client: tuple[TestClient, Any, Any],
    ) -> None:
        """should append to verified_contacts.pii_access_audit_logs."""
        client, contact, user = unlock_client

        response = client.post(
            f"/api/v1/workspaces/1/leads/{contact.lead_id}/contacts/{contact.id}/unlock"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["contact_id"] == str(contact.id)
        assert data["is_unlocked"] is True
        assert data["cost_micros"] == 1500

        assert contact.is_unlocked is True
        assert len(contact.pii_access_audit_logs) == 1
        log = contact.pii_access_audit_logs[0]
        assert log["user_id"] == str(user.id)
        assert log["workspace_id"] == 1
        assert log["lead_id"] == str(contact.lead_id)
        assert log["contact_id"] == str(contact.id)
        assert log["access_type"] == "unlock"
        assert "timestamp" in log
