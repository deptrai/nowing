"""Red-phase ATDD tests for Story 21.1 signal-scan billing.

Tests the ``record_signal_scan`` helper / ``BillingEventService`` contract. DB
and wallet are mocked; no real Postgres or credit card gateway is required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.services.etl_credit_service import InsufficientCreditsError

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """AsyncSession stand-in that records staged rows and transaction state."""

    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
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

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, _obj: Any) -> None:
        pass

    async def flush(self) -> None:
        self.flushed = True


def _billing_event_rows(session: _FakeSession) -> list[Any]:
    return [o for o in session.added if type(o).__name__ == "BillingEvent"]


def _patch_wallet(monkeypatch, *, balance_micros: int = 1_000_000) -> dict[str, Any]:
    """Replace wallet primitives with AsyncMock spies."""
    calls: dict[str, Any] = {"check": [], "debit": []}

    async def _check_balance(_session: Any, user_id: Any, required_micros: int) -> None:
        calls["check"].append({"user_id": user_id, "required_micros": required_micros})
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
        self,
        *,
        workspace_id: int,
        user_id: Any,
        amount_micros: int,
        description: str = "",
    ) -> dict[str, Any]:
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
        "app.services.workspace_credit_service.WorkspaceCreditService.record_spend",
        _record_spend,
        raising=False,
    )
    return calls


class TestRecordSignalScan:
    """AC-6: BillingEvent ledger and wallet debit contract."""

    @pytest.mark.asyncio
    async def test_record_signal_scan_writes_billing_event_with_exact_fields(
        self, monkeypatch
    ):
        from app.services.billing_event_service import record_signal_scan

        _patch_wallet(monkeypatch)
        session = _FakeSession()
        signal_event_id = uuid4()

        await record_signal_scan(
            session,
            signal_event_id=signal_event_id,
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=3000,
        )

        rows = _billing_event_rows(session)
        assert rows
        row = rows[0]
        assert row.event_entity_type == "signal_event"
        assert row.event_type == "signal_scan"
        assert row.event_id == signal_event_id
        assert row.cost_micros == 3000
        assert row.workspace_id == 1

    @pytest.mark.asyncio
    async def test_record_signal_scan_defaults_currency_and_cost_basis(
        self, monkeypatch
    ):
        from app.services.billing_event_service import record_signal_scan

        _patch_wallet(monkeypatch)
        session = _FakeSession()

        await record_signal_scan(
            session,
            signal_event_id=uuid4(),
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=1000,
        )

        row = _billing_event_rows(session)[0]
        assert row.currency == "USD"
        assert row.cost_basis == "estimated"

    @pytest.mark.asyncio
    async def test_record_signal_scan_calls_wallet_check_balance_and_apply_debit(
        self, monkeypatch
    ):
        from app.services.billing_event_service import record_signal_scan

        calls = _patch_wallet(monkeypatch)
        session = _FakeSession()
        user_id = uuid4()

        await record_signal_scan(
            session,
            signal_event_id=uuid4(),
            workspace_id=1,
            client_id=None,
            user_id=user_id,
            cost_micros=2500,
        )

        assert len(calls["check"]) == 1
        assert calls["check"][0]["user_id"] == user_id
        assert calls["check"][0]["required_micros"] == 2500
        assert len(calls["debit"]) == 1
        assert calls["debit"][0]["user_id"] == user_id
        assert calls["debit"][0]["cost_micros"] == 2500

    @pytest.mark.asyncio
    async def test_record_signal_scan_cost_micros_equals_computed_value(
        self, monkeypatch
    ):
        from app.config import config
        from app.services.billing_event_service import record_signal_scan

        monkeypatch.setattr(
            config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 1500, raising=False
        )
        _patch_wallet(monkeypatch)
        session = _FakeSession()

        # The helper is expected to compute N * unit_cost when given item count.
        await record_signal_scan(
            session,
            signal_event_id=uuid4(),
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=3 * 1500,
        )

        row = _billing_event_rows(session)[0]
        assert row.cost_micros == 4500

    @pytest.mark.asyncio
    async def test_record_signal_scan_zero_cost_writes_billing_event_with_zero(
        self, monkeypatch
    ):
        from app.config import config
        from app.services.billing_event_service import record_signal_scan

        monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 0, raising=False)
        _patch_wallet(monkeypatch)
        session = _FakeSession()

        await record_signal_scan(
            session,
            signal_event_id=uuid4(),
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=0,
        )

        rows = _billing_event_rows(session)
        assert rows
        assert rows[0].cost_micros == 0

    @pytest.mark.asyncio
    async def test_record_signal_scan_rejects_negative_cost(self):
        from app.services.billing_event_service import record_signal_scan

        session = _FakeSession()

        with pytest.raises(ValueError, match="cost_micros"):
            await record_signal_scan(
                session,
                signal_event_id=uuid4(),
                workspace_id=1,
                client_id=None,
                user_id=uuid4(),
                cost_micros=-100,
            )

    @pytest.mark.asyncio
    async def test_record_signal_scan_no_signal_event_id_writes_no_billing_event(
        self, monkeypatch
    ):
        from app.services.billing_event_service import record_signal_scan

        _patch_wallet(monkeypatch)
        session = _FakeSession()

        await record_signal_scan(
            session,
            signal_event_id=None,  # type: ignore[arg-type]
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=1000,
        )

        assert not _billing_event_rows(session)

    @pytest.mark.asyncio
    async def test_record_signal_scan_insufficient_credits_raises_with_message(
        self, monkeypatch
    ):
        from app.services.billing_event_service import record_signal_scan

        _patch_wallet(monkeypatch, balance_micros=0)
        session = _FakeSession()

        with pytest.raises(InsufficientCreditsError) as exc_info:
            await record_signal_scan(
                session,
                signal_event_id=uuid4(),
                workspace_id=1,
                client_id=None,
                user_id=uuid4(),
                cost_micros=1000,
            )

        assert "exceed your available credit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_record_signal_scan_apply_debit_failure_refunds_member_spend(
        self, monkeypatch
    ):
        from app.services.billing_event_service import record_signal_scan

        async def _apply_debit(_session: Any, _user_id: Any, _cost_micros: int) -> int:
            raise RuntimeError("debit failed")

        record_spend_calls: list[dict[str, Any]] = []

        async def _record_spend(
            self,
            *,
            workspace_id: int,
            user_id: Any,
            amount_micros: int,
            description: str = "",
        ) -> dict[str, Any]:
            record_spend_calls.append(
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
                "member_monthly_spent": amount_micros,
                "member_monthly_spend_cap": None,
            }

        refund_calls: list[dict[str, Any]] = []

        async def _refund_member_spend(
            self,
            *,
            workspace_id: int,
            user_id: Any,
            amount_micros: int,
        ) -> dict[str, Any]:
            refund_calls.append(
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
                "member_monthly_spend_cap": None,
            }

        monkeypatch.setattr(
            "app.services.wallet_credit.apply_debit",
            _apply_debit,
            raising=False,
        )
        monkeypatch.setattr(
            "app.services.wallet_credit.check_balance",
            AsyncMock(),
            raising=False,
        )
        monkeypatch.setattr(
            "app.services.workspace_credit_service.WorkspaceCreditService.record_spend",
            _record_spend,
            raising=False,
        )
        monkeypatch.setattr(
            "app.services.workspace_credit_service.WorkspaceCreditService.refund_member_spend",
            _refund_member_spend,
            raising=False,
        )

        session = _FakeSession()

        user_id = uuid4()
        with pytest.raises(RuntimeError, match="debit failed"):
            await record_signal_scan(
                session,
                signal_event_id=uuid4(),
                workspace_id=1,
                client_id=None,
                user_id=user_id,
                cost_micros=1000,
            )

        assert record_spend_calls == [
            {"workspace_id": 1, "user_id": user_id, "amount_micros": 1000}
        ]
        assert refund_calls == [
            {"workspace_id": 1, "user_id": user_id, "amount_micros": 1000}
        ]
        assert session.rolled_back is False
        assert session.committed is False

    @pytest.mark.asyncio
    async def test_record_signal_scan_does_not_double_charge_same_signal_event(
        self, monkeypatch
    ):
        from app.services.billing_event_service import record_signal_scan

        _patch_wallet(monkeypatch)
        session = _FakeSession()
        signal_event_id = uuid4()

        # First call succeeds.
        await record_signal_scan(
            session,
            signal_event_id=signal_event_id,
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=1000,
        )

        # Second call for the same signal event should raise or skip.
        with pytest.raises(ValueError, match="duplicate"):
            await record_signal_scan(
                session,
                signal_event_id=signal_event_id,
                workspace_id=1,
                client_id=None,
                user_id=uuid4(),
                cost_micros=1000,
            )


class TestBillingEventService:
    """AC-6: class-based API is also exposed."""

    @pytest.mark.asyncio
    async def test_billing_event_service_record_scan_exists(self, monkeypatch):
        from app.services.billing_event_service import BillingEventService

        _patch_wallet(monkeypatch)
        service = BillingEventService()
        session = _FakeSession()
        signal_event_id = uuid4()

        await service.record_scan(
            session,
            signal_event_id=signal_event_id,
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=1000,
        )

        rows = _billing_event_rows(session)
        assert rows
        assert rows[0].event_id == signal_event_id


class TestRecordContactEnrichment:
    """AC-7: contact-enrichment billing uses cost_basis='actual'."""

    @pytest.mark.asyncio
    async def test_writes_billing_event_with_exact_fields(self, monkeypatch):
        from app.services.billing_event_service import BillingEventService

        service = BillingEventService()

        _patch_wallet(monkeypatch)
        session = _FakeSession()
        enrichment_request_id = uuid4()
        user_id = uuid4()

        await service.record_contact_enrichment(
            session,
            enrichment_request_id=enrichment_request_id,
            workspace_id=1,
            client_id=None,
            user_id=user_id,
            cost_micros=2500,
        )

        row = _billing_event_rows(session)[0]
        assert row.event_entity_type == "enrichment_request"
        assert row.event_type == "contact_enrichment"
        assert row.event_id == enrichment_request_id
        assert row.cost_micros == 2500
        assert row.workspace_id == 1

    @pytest.mark.asyncio
    async def test_uses_actual_cost_basis_and_currency_usd(self, monkeypatch):
        from app.services.billing_event_service import BillingEventService

        service = BillingEventService()

        _patch_wallet(monkeypatch)
        session = _FakeSession()

        await service.record_contact_enrichment(
            session,
            enrichment_request_id=uuid4(),
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=1000,
        )

        row = _billing_event_rows(session)[0]
        assert row.currency == "USD"
        assert row.cost_basis == "actual"

    @pytest.mark.asyncio
    async def test_calls_wallet_check_balance_and_apply_debit(self, monkeypatch):
        from app.services.billing_event_service import BillingEventService

        service = BillingEventService()

        calls = _patch_wallet(monkeypatch)
        session = _FakeSession()
        user_id = uuid4()

        await service.record_contact_enrichment(
            session,
            enrichment_request_id=uuid4(),
            workspace_id=1,
            client_id=None,
            user_id=user_id,
            cost_micros=1000,
        )

        assert calls["check"] == [{"user_id": user_id, "required_micros": 1000}]
        assert calls["debit"] == [{"user_id": user_id, "cost_micros": 1000}]

    @pytest.mark.asyncio
    async def test_zero_cost_writes_event_without_debit(self, monkeypatch):
        from app.services.billing_event_service import BillingEventService

        service = BillingEventService()

        calls = _patch_wallet(monkeypatch)
        session = _FakeSession()

        await service.record_contact_enrichment(
            session,
            enrichment_request_id=uuid4(),
            workspace_id=1,
            client_id=None,
            user_id=uuid4(),
            cost_micros=0,
        )

        row = _billing_event_rows(session)[0]
        assert row.cost_micros == 0
        assert calls["debit"] == []

    @pytest.mark.asyncio
    async def test_insufficient_credits_raises(self, monkeypatch):
        from app.services.billing_event_service import BillingEventService

        service = BillingEventService()

        _patch_wallet(monkeypatch, balance_micros=500)
        session = _FakeSession()

        with pytest.raises(InsufficientCreditsError) as exc_info:
            await service.record_contact_enrichment(
                session,
                enrichment_request_id=uuid4(),
                workspace_id=1,
                client_id=None,
                user_id=uuid4(),
                cost_micros=1000,
            )
        assert "exceed your available credit" in str(exc_info.value)


class TestRecordContactUnlockRefund24h:
    """AC-4: 24h auto-refund SLA with 15% billing-cycle cap (Story 26.6)."""

    def _make_unlock_event(
        self, contact_id: UUID, user_id: UUID, created_at: datetime | None = None
    ) -> Any:
        from types import SimpleNamespace

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

    def _make_refund_event(self, contact_id: UUID, user_id: UUID) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            workspace_id=1,
            event_entity_type="verified_contact",
            event_type="contact_unlock_refund",
            event_id=contact_id,
            cost_micros=-1500,
            created_at=datetime.now(UTC),
        )

    def _patch_wallet_and_spend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, Any]:
        calls: dict[str, Any] = {"credit": [], "refund_spend": []}

        async def _apply_credit(_session: Any, user_id: Any, amount_micros: int) -> int:
            calls["credit"].append({"user_id": user_id, "amount_micros": amount_micros})
            return amount_micros

        async def _refund_member_spend(
            self: Any,
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

        monkeypatch.setattr(
            "app.services.wallet_credit.apply_credit", _apply_credit, raising=False
        )
        monkeypatch.setattr(
            "app.services.workspace_credit_service.WorkspaceCreditService.refund_member_spend",
            _refund_member_spend,
            raising=False,
        )
        return calls

    def _compile_text(self, stmt: Any) -> str:
        try:
            return str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        except Exception:
            return str(stmt).lower()

    @pytest.mark.asyncio
    async def test_record_contact_unlock_refund_24h_returns_negative_billing_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P0: record_contact_unlock_refund_24h writes -1500 micros BillingEvent and credits wallet."""
        from app.services.billing_event_service import BillingEventService

        calls = self._patch_wallet_and_spend(monkeypatch)
        contact_id = uuid4()
        user_id = uuid4()
        original_unlock = self._make_unlock_event(contact_id, user_id)

        session = _FakeSession()

        # Mock query results
        async def _execute(stmt: Any, _params: Any | None = None) -> _FakeResult:
            text = self._compile_text(stmt)
            if "contact_unlock_refund" in text and "count" in text:
                return _FakeResult(value=0)
            if "contact_unlock" in text and "count" in text:
                return _FakeResult(value=10)
            if "contact_unlock_refund" in text:
                return _FakeResult(rows=[])  # no existing refund
            if "contact_unlock" in text:
                return _FakeResult(value=original_unlock, rows=[original_unlock])
            return _FakeResult(value=1, rows=[])

        session.execute = _execute  # type: ignore[method-assign]

        result = await BillingEventService().record_contact_unlock_refund_24h(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )

        assert result.event_type == "contact_unlock_refund"
        assert result.cost_micros == -1500
        assert len(calls["credit"]) == 1
        assert calls["credit"][0]["amount_micros"] == 1500
        assert len(calls["refund_spend"]) == 1
        assert calls["refund_spend"][0]["amount_micros"] == 1500

    @pytest.mark.asyncio
    async def test_record_contact_unlock_refund_24h_is_idempotent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P0: a second refund call for the same contact returns existing event without double credit."""
        from app.services.billing_event_service import BillingEventService

        calls = self._patch_wallet_and_spend(monkeypatch)
        contact_id = uuid4()
        user_id = uuid4()
        existing_refund = self._make_refund_event(contact_id, user_id)

        session = _FakeSession()

        async def _execute(stmt: Any, _params: Any | None = None) -> _FakeResult:
            text = self._compile_text(stmt)
            if "contact_unlock_refund" in text:
                return _FakeResult(value=existing_refund, rows=[existing_refund])
            return _FakeResult()

        session.execute = _execute  # type: ignore[method-assign]

        result = await BillingEventService().record_contact_unlock_refund_24h(
            session,
            verified_contact_id=contact_id,
            workspace_id=1,
            user_id=user_id,
        )

        assert result is existing_refund
        assert len(calls["credit"]) == 0
        assert len(calls["refund_spend"]) == 0

    @pytest.mark.asyncio
    async def test_record_contact_unlock_refund_24h_refuses_if_relocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Patch: a refund call for a contact already relocked is rejected to avoid conflating the ledger."""
        from types import SimpleNamespace

        from app.services.billing_event_service import (
            BillingEventService,
            RefundAlreadyProcessedError,
        )

        calls = self._patch_wallet_and_spend(monkeypatch)
        contact_id = uuid4()
        user_id = uuid4()
        existing_relock = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            workspace_id=1,
            event_entity_type="verified_contact",
            event_type="contact_relock",
            event_id=contact_id,
            cost_micros=-1500,
            created_at=datetime.now(UTC),
        )

        session = _FakeSession()

        async def _execute(stmt: Any, _params: Any | None = None) -> _FakeResult:
            text = self._compile_text(stmt)
            if "contact_unlock_refund" in text:
                return _FakeResult(rows=[])
            if "contact_relock" in text:
                return _FakeResult(value=existing_relock, rows=[existing_relock])
            return _FakeResult()

        session.execute = _execute  # type: ignore[method-assign]

        with pytest.raises(RefundAlreadyProcessedError):
            await BillingEventService().record_contact_unlock_refund_24h(
                session,
                verified_contact_id=contact_id,
                workspace_id=1,
                user_id=user_id,
            )

        assert len(calls["credit"]) == 0
        assert len(calls["refund_spend"]) == 0

    @pytest.mark.asyncio
    async def test_record_contact_unlock_refund_24h_refuses_expired_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P0: refund beyond 24h window is rejected with ValueError."""
        from datetime import timedelta

        from app.services.billing_event_service import BillingEventService

        self._patch_wallet_and_spend(monkeypatch)
        contact_id = uuid4()
        user_id = uuid4()
        expired_unlock = self._make_unlock_event(
            contact_id, user_id, created_at=datetime.now(UTC) - timedelta(hours=25)
        )

        session = _FakeSession()

        async def _execute(stmt: Any, _params: Any | None = None) -> _FakeResult:
            text = self._compile_text(stmt)
            if "contact_unlock_refund" in text:
                return _FakeResult(rows=[])
            if "contact_unlock" in text:
                return _FakeResult(value=expired_unlock, rows=[expired_unlock])
            return _FakeResult(value=10)

        session.execute = _execute  # type: ignore[method-assign]

        with pytest.raises((ValueError, RuntimeError), match=r"(?i)24h|expired|window"):
            await BillingEventService().record_contact_unlock_refund_24h(
                session,
                verified_contact_id=contact_id,
                workspace_id=1,
                user_id=user_id,
            )

    @pytest.mark.asyncio
    async def test_record_contact_unlock_refund_24h_refuses_when_no_original_unlock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P0: refund without prior contact_unlock BillingEvent is rejected."""
        from app.services.billing_event_service import BillingEventService

        self._patch_wallet_and_spend(monkeypatch)
        session = _FakeSession()

        async def _execute(stmt: Any, _params: Any | None = None) -> _FakeResult:
            return _FakeResult(value=None, rows=[])

        session.execute = _execute  # type: ignore[method-assign]

        with pytest.raises(
            (ValueError, RuntimeError), match=r"(?i)original|not found|unlock"
        ):
            await BillingEventService().record_contact_unlock_refund_24h(
                session,
                verified_contact_id=uuid4(),
                workspace_id=1,
                user_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_record_contact_unlock_refund_24h_refuses_when_cap_exhausted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P0: refund rejected when 15% budget cap is reached."""
        from app.services.billing_event_service import BillingEventService

        self._patch_wallet_and_spend(monkeypatch)
        contact_id = uuid4()
        user_id = uuid4()
        original_unlock = self._make_unlock_event(contact_id, user_id)

        session = _FakeSession()

        dummy_refunds = [self._make_refund_event(uuid4(), user_id) for _ in range(15)]
        dummy_unlocks = [self._make_unlock_event(uuid4(), user_id) for _ in range(100)]

        # Simulate 100 unlocks and 15 prior refunds (cap = 15) -> 16th refund is rejected
        async def _execute(stmt: Any, _params: Any | None = None) -> _FakeResult:
            text = self._compile_text(stmt)
            # Cycle count queries contain 'created_at >='
            if "created_at >=" in text:
                if "contact_unlock_refund" in text:
                    return _FakeResult(rows=dummy_refunds)
                if "contact_unlock" in text:
                    return _FakeResult(rows=dummy_unlocks)
            # Identity queries for this specific contact
            if "contact_unlock_refund" in text:
                return _FakeResult(rows=[])
            if "contact_unlock" in text:
                return _FakeResult(value=original_unlock, rows=[original_unlock])
            return _FakeResult()

        session.execute = _execute  # type: ignore[method-assign]

        with pytest.raises(
            (ValueError, RuntimeError), match=r"(?i)cap|budget|exhausted|limit"
        ):
            await BillingEventService().record_contact_unlock_refund_24h(
                session,
                verified_contact_id=contact_id,
                workspace_id=1,
                user_id=user_id,
            )
