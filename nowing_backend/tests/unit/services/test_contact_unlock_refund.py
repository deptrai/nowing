"""Red-phase unit tests for contact-unlock refund (Story 26.4)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.config import config
from app.services.billing_event_service import BillingEventService
from app.services.workspace_credit_service import WorkspaceCreditService

pytestmark = pytest.mark.unit


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
    def __init__(self, event: Any | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._event = event

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._event)

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


def _make_unlock_billing_event(user_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        cost_micros=1500,
        event_type="contact_unlock",
    )


class TestRecordContactUnlockRefund:
    """AC-3/AC-5: refund credit when a verified contact is opted out."""

    @pytest.fixture(autouse=True)
    def _fixed_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "SECRET_KEY", "test-secret")

    @pytest.mark.asyncio
    async def test_refund_credits_user_wallet_and_monthly_spent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payer_id = uuid4()
        contact_id = uuid4()
        original = _make_unlock_billing_event(payer_id)
        session = _FakeSession(event=original)

        calls: dict[str, Any] = {"wallet": [], "monthly_spent": []}

        async def _apply_credit(_session: Any, user_id: Any, amount_micros: int) -> int:
            calls["wallet"].append({"user_id": user_id, "amount_micros": amount_micros})
            return 1500

        async def _refund_member_spend(
            self: WorkspaceCreditService,
            *,
            workspace_id: int,
            user_id: UUID,
            amount_micros: int,
        ) -> dict[str, Any]:
            calls["monthly_spent"].append(
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

        monkeypatch.setattr(
            "app.services.billing_event_service.wallet_credit.apply_credit",
            _apply_credit,
        )
        monkeypatch.setattr(
            WorkspaceCreditService,
            "refund_member_spend",
            _refund_member_spend,
        )

        result = await BillingEventService().record_contact_unlock_refund(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=uuid4(),
        )

        assert result.cost_micros == -1500
        assert result.event_type == "contact_unlock_refund"
        assert result.event_entity_type == "verified_contact"
        assert result.event_id == contact_id

        assert len(calls["wallet"]) == 1
        assert calls["wallet"][0]["amount_micros"] == 1500
        assert calls["wallet"][0]["user_id"] == payer_id
        assert len(calls["monthly_spent"]) == 1
        assert calls["monthly_spent"][0]["amount_micros"] == 1500

    @pytest.mark.asyncio
    async def test_refund_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payer_id = uuid4()
        contact_id = uuid4()
        existing_refund = SimpleNamespace(
            id=uuid4(),
            event_type="contact_unlock_refund",
            cost_micros=-1500,
        )
        session = _FakeSession(event=existing_refund)

        calls: dict[str, Any] = {"wallet": []}

        async def _apply_credit(*args: Any, **kwargs: Any) -> None:
            calls["wallet"].append({"args": args, "kwargs": kwargs})

        monkeypatch.setattr(
            "app.services.billing_event_service.wallet_credit.apply_credit",
            _apply_credit,
        )

        result = await BillingEventService().record_contact_unlock_refund(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=payer_id,
        )

        assert result is existing_refund
        assert not calls["wallet"]
        assert not session.added

    @pytest.mark.asyncio
    async def test_refund_fails_when_no_original_billing_event(self) -> None:
        session = _FakeSession(event=None)

        with pytest.raises(ValueError, match="no unlock billing event"):
            await BillingEventService().record_contact_unlock_refund(
                session,
                verified_contact_id=uuid4(),
                workspace_id=1,
                user_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_refund_does_not_credit_workspace_pool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WorkspaceCreditService.refund_credits touches workspace pool; refund must not."""
        payer_id = uuid4()
        contact_id = uuid4()
        original = _make_unlock_billing_event(payer_id)
        session = _FakeSession(event=original)

        workspace_balance_calls: list[Any] = []

        async def _refund_credits(
            self: WorkspaceCreditService,
            *,
            workspace_id: int,
            user_id: UUID,
            amount_micros: int,
            reason: str = "",
        ) -> dict[str, Any]:
            workspace_balance_calls.append({"amount_micros": amount_micros})
            return {}

        async def _refund_member_spend(
            self: WorkspaceCreditService,
            *,
            workspace_id: int,
            user_id: UUID,
            amount_micros: int,
        ) -> dict[str, Any]:
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": amount_micros,
                "member_monthly_spent": 0,
            }

        async def _apply_credit(_session: Any, user_id: Any, amount_micros: int) -> int:
            return amount_micros

        monkeypatch.setattr(
            WorkspaceCreditService,
            "refund_credits",
            _refund_credits,
        )
        monkeypatch.setattr(
            WorkspaceCreditService,
            "refund_member_spend",
            _refund_member_spend,
        )
        monkeypatch.setattr(
            "app.services.billing_event_service.wallet_credit.apply_credit",
            _apply_credit,
        )

        await BillingEventService().record_contact_unlock_refund(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=payer_id,
        )

        assert not workspace_balance_calls
