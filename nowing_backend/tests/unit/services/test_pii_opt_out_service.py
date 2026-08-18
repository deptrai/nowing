"""Red-phase unit tests for PII opt-out service (Story 26.4)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.config import config
from app.services.pii.opt_out_service import OptOutService

pytestmark = [pytest.mark.unit]


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
    def __init__(self, contacts: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.flushed = False
        self._contacts = contacts or []
        self._dnc: Any | None = None

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(rows=self._contacts)

    async def get(self, _model: type, _ident: Any) -> Any | None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, _obj: Any) -> None:
        pass


class TestOptOutServiceProcess:
    """AC-3: PII opt-out purges contacts and refunds credit."""

    @pytest.fixture(autouse=True)
    def _fixed_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "SECRET_KEY", "test-secret")

    def _make_unlocked_contact(self) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid4(),
            workspace_id=1,
            lead_id=uuid4(),
            phone="encrypted-phone",
            email="encrypted-email",
            name="Alice",
            title="CEO",
            phone_hmac="phone-hash",
            email_hmac="email-hash",
            value_hmac="contact-hmac",
            is_unlocked=True,
            consent=True,
            consent_status="opted_in",
            legal_basis="consent",
            pii_access_audit_logs=[],
        )

    @pytest.mark.asyncio
    async def test_opt_out_creates_dnc_record_and_purges(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        contact = self._make_unlocked_contact()
        session = _FakeSession(contacts=[contact])

        class FakeDncService:
            def __init__(self, **kwargs: Any) -> None:
                pass

            async def invalidate_workspace_cache(
                self, *args: Any, **kwargs: Any
            ) -> None:
                pass

        monkeypatch.setattr(
            "app.services.pii.opt_out_service.DncComplianceService",
            FakeDncService,
        )

        service = OptOutService(session)
        result = await service.process_opt_out(
            workspace_id=1,
            record_type="phone",
            value="+84908123456",
            actor_user_id=uuid4(),
            ip_address="1.2.3.4",
        )

        assert result.purged_contact_count == 1
        assert result.dnc_record_id is not None
        assert contact.is_unlocked is False
        assert contact.consent is False
        assert contact.consent_status == "withdrawn"
        assert contact.legal_basis == "opt_out"
        assert contact.name is None
        assert contact.title is None
        assert contact.phone is None
        assert contact.email is None

        assert len(contact.pii_access_audit_logs) == 1
        log = contact.pii_access_audit_logs[0]
        assert log["access_type"] == "opt_out_purged"
        assert log["ip_address"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_opt_out_refunds_per_unlocked_contact(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        contact = self._make_unlocked_contact()
        original_event = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            cost_micros=1500,
        )

        session = _FakeSession(contacts=[contact])

        calls: dict[str, Any] = {"wallet": [], "monthly_spent": []}

        async def _credit_wallet(
            _s: Any, user_id: UUID | str, amount_micros: int
        ) -> None:
            calls["wallet"].append({"user_id": user_id, "amount_micros": amount_micros})

        async def _decrement_monthly_spent(
            _s: Any, *, workspace_id: int, user_id: UUID, amount_micros: int
        ) -> None:
            calls["monthly_spent"].append(
                {
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "amount_micros": amount_micros,
                }
            )

        monkeypatch.setattr(
            "app.services.pii.opt_out_service._credit_user_wallet",
            _credit_wallet,
        )
        monkeypatch.setattr(
            "app.services.pii.opt_out_service._decrement_member_monthly_spent",
            _decrement_monthly_spent,
        )

        async def _find_original_event(
            _session: Any, _contact_id: UUID, _workspace_id: int
        ) -> Any:
            return original_event

        monkeypatch.setattr(
            "app.services.pii.opt_out_service._find_original_unlock_billing_event",
            _find_original_event,
        )

        service = OptOutService(session)
        result = await service.process_opt_out(
            workspace_id=1,
            record_type="phone",
            value="+84908123456",
            actor_user_id=uuid4(),
        )

        assert result.refunded_micros == 1500
        assert len(calls["wallet"]) == 1
        assert calls["wallet"][0]["amount_micros"] == 1500
        assert calls["wallet"][0]["user_id"] == original_event.user_id
        assert len(calls["monthly_spent"]) == 1
        assert calls["monthly_spent"][0]["amount_micros"] == 1500

        refund_event = next(
            (
                a
                for a in session.added
                if getattr(a, "event_type", None) == "contact_unlock_refund"
            ),
            None,
        )
        assert refund_event is not None
        assert refund_event.cost_micros == -1500

    @pytest.mark.asyncio
    async def test_opt_out_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        contact = self._make_unlocked_contact()
        contact.is_unlocked = False
        session = _FakeSession(contacts=[contact])

        service = OptOutService(session)
        result = await service.process_opt_out(
            workspace_id=1,
            record_type="phone",
            value="+84908123456",
            actor_user_id=uuid4(),
        )

        assert result.purged_contact_count == 1
        assert result.refunded_micros == 0

    @pytest.mark.asyncio
    async def test_opt_out_respects_15_percent_refund_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        contact = self._make_unlocked_contact()
        session = _FakeSession(contacts=[contact])

        # Simulate cap exhausted: already refunded 15% this cycle.
        async def _no_refunds(*a: Any, **k: Any) -> int:
            return 0

        monkeypatch.setattr(
            "app.services.pii.opt_out_service._count_refundable_unlocks_this_cycle",
            _no_refunds,
        )

        service = OptOutService(session)
        result = await service.process_opt_out(
            workspace_id=1,
            record_type="phone",
            value="+84908123456",
            actor_user_id=uuid4(),
        )

        assert result.purged_contact_count == 1
        assert result.refunded_micros == 0

    @pytest.mark.asyncio
    async def test_opt_out_no_matching_contact_still_creates_dnc(self) -> None:
        session = _FakeSession(contacts=[])
        service = OptOutService(session)

        result = await service.process_opt_out(
            workspace_id=1,
            record_type="phone",
            value="+84900000000",
            actor_user_id=uuid4(),
        )

        assert result.purged_contact_count == 0
        assert result.refunded_micros == 0
        assert result.dnc_record_id is not None
