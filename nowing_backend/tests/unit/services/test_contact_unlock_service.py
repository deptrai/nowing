"""Red-phase ATDD unit tests for ContactUnlockService (Story 26.6 / 26.5 shared service).

Tests the shared contact unlock service used by both REST endpoints and Telegram callbacks.
DB and external encryption are mocked for pure unit testing.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.etl_credit_service import InsufficientCreditsError

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


def _make_contact(overrides: dict | None = None) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "workspace_id": 1,
        "lead_id": uuid4(),
        "phone": "enc_phone_token_123",
        "email": "enc_email_token_123",
        "name": "enc_name_token_123",
        "title": "CEO",
        "is_unlocked": False,
        "is_valid": True,
        "consent_status": "opted_in",
        "pii_access_audit_logs": [],
        "value_hmac": "contact-hmac",
        "phone_hmac": "phone-hmac",
        "email_hmac": "email-hmac",
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestContactUnlockService:
    """Core contact unlock business logic tests."""

    @pytest.mark.asyncio
    async def test_unlock_contact_success_debits_wallet_and_decrypts_pii(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 1: Successful unlock debits 1,500 micros, decrypts PII, appends audit."""
        from app.services.contact_unlock_service import ContactUnlockService

        session = _FakeSession()
        contact = _make_contact({"is_unlocked": False})
        user_id = uuid4()

        # Mock dependencies
        mocker.patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.is_blocked",
            new=AsyncMock(return_value=SimpleNamespace(is_blocked=False, reason=None)),
        )
        mocker.patch(
            "app.services.pii.verified_contact_encryption.VerifiedContactEncryption.decrypt",
            side_effect=lambda val, **kw: {
                "enc_phone_token_123": "0908123456",
                "enc_email_token_123": "alice@acme.vn",
                "enc_name_token_123": "Nguyễn Văn A",
            }.get(val, val),
        )
        record_unlock = mocker.patch(
            "app.services.billing_event_service.BillingEventService.record_contact_unlock",
            new=AsyncMock(return_value=SimpleNamespace(cost_micros=1500)),
        )

        service = ContactUnlockService()
        result = await service.unlock_contact(
            session=session,
            workspace_id=1,
            contact=contact,
            user_id=user_id,
            reason="telegram_unlock",
        )

        assert result.is_unlocked is True
        assert result.cost_micros == 1500
        assert result.phone == "0908123456"
        assert result.email == "alice@acme.vn"
        assert result.name == "Nguyễn Văn A"
        assert contact.is_unlocked is True

        # Assert BillingEventService was called with 1500 micros
        record_unlock.assert_awaited_once()
        # Assert audit log was recorded
        assert len(contact.pii_access_audit_logs) == 1
        assert contact.pii_access_audit_logs[0]["access_type"] == "unlock"

    @pytest.mark.asyncio
    async def test_unlock_contact_already_unlocked_is_idempotent_zero_cost(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 1: Already unlocked contact returns decrypted PII with cost_micros=0."""
        from app.services.contact_unlock_service import ContactUnlockService

        session = _FakeSession()
        contact = _make_contact({"is_unlocked": True})
        user_id = uuid4()

        mocker.patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.is_blocked",
            new=AsyncMock(return_value=SimpleNamespace(is_blocked=False, reason=None)),
        )
        mocker.patch(
            "app.services.pii.verified_contact_encryption.VerifiedContactEncryption.decrypt",
            return_value="0908123456",
        )
        record_unlock = mocker.patch(
            "app.services.billing_event_service.BillingEventService.record_contact_unlock",
            new=AsyncMock(),
        )

        service = ContactUnlockService()
        result = await service.unlock_contact(
            session=session,
            workspace_id=1,
            contact=contact,
            user_id=user_id,
            reason="telegram_unlock",
        )

        assert result.is_unlocked is True
        assert result.cost_micros == 0
        record_unlock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unlock_contact_blocked_by_dnc_raises_403(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 2: DNC blocked contact raises 403 Forbidden fail-closed."""
        from app.services.contact_unlock_service import ContactUnlockService

        session = _FakeSession()
        contact = _make_contact()
        user_id = uuid4()

        mocker.patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.is_blocked",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    is_blocked=True, reason="National DNC list match"
                )
            ),
        )

        service = ContactUnlockService()
        with pytest.raises(HTTPException) as exc_info:
            await service.unlock_contact(
                session=session,
                workspace_id=1,
                contact=contact,
                user_id=user_id,
            )

        assert exc_info.value.status_code == 403
        assert "DNC" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_unlock_contact_withdrawn_consent_raises_409(self) -> None:
        """Pattern 3 (Edge): Withdrawn consent raises 409 Conflict."""
        from app.services.contact_unlock_service import ContactUnlockService

        session = _FakeSession()
        contact = _make_contact({"consent_status": "withdrawn"})
        user_id = uuid4()

        service = ContactUnlockService()
        with pytest.raises(HTTPException) as exc_info:
            await service.unlock_contact(
                session=session,
                workspace_id=1,
                contact=contact,
                user_id=user_id,
            )

        assert exc_info.value.status_code == 409
        assert (
            "consent" in str(exc_info.value.detail).lower()
            or "withdrawn" in str(exc_info.value.detail).lower()
        )

    @pytest.mark.asyncio
    async def test_unlock_contact_invalid_contact_raises_409(self) -> None:
        """Pattern 3 (Edge): Invalid contact raises 409 Conflict."""
        from app.services.contact_unlock_service import ContactUnlockService

        session = _FakeSession()
        contact = _make_contact({"is_valid": False})
        user_id = uuid4()

        service = ContactUnlockService()
        with pytest.raises(HTTPException) as exc_info:
            await service.unlock_contact(
                session=session,
                workspace_id=1,
                contact=contact,
                user_id=user_id,
            )

        assert exc_info.value.status_code == 409
        assert "invalid" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_unlock_contact_insufficient_credits_raises_402(
        self, mocker: pytest.MonkeyPatch
    ) -> None:
        """Pattern 2: Low wallet balance raises 402 Payment Required."""
        from app.services.contact_unlock_service import ContactUnlockService

        session = _FakeSession()
        contact = _make_contact()
        user_id = uuid4()

        mocker.patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.is_blocked",
            new=AsyncMock(return_value=SimpleNamespace(is_blocked=False, reason=None)),
        )
        mocker.patch(
            "app.services.billing_event_service.BillingEventService.record_contact_unlock",
            new=AsyncMock(
                side_effect=InsufficientCreditsError(
                    "Insufficient balance", balance_micros=500, required_micros=1500
                )
            ),
        )

        service = ContactUnlockService()
        with pytest.raises((InsufficientCreditsError, HTTPException)) as exc_info:
            await service.unlock_contact(
                session=session,
                workspace_id=1,
                contact=contact,
                user_id=user_id,
            )

        if isinstance(exc_info.value, HTTPException):
            assert exc_info.value.status_code == 402
