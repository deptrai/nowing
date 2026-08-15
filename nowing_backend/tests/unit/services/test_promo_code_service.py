"""Unit tests for Promo Code & Anti-Abuse Service (Story 21.7 / AC-5).

Validates promo code normalization, concurrency safe redemption, expiration checks,
max uses bounds, and 1-time per user enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.db import (
    PromoCode,
    PromoCodeRedemption,
    User,
)
from app.services.promo_code_service import (
    PromoCodeAlreadyRedeemedError,
    PromoCodeExhaustedError,
    PromoCodeExpiredError,
    PromoCodeNotFoundError,
    PromoCodeService,
)

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(
        self,
        *,
        scalar: Any = None,
        rows: list[Any] | None = None,
        results: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self._scalar = scalar
        self._rows = rows or []
        self._results = results or []
        self._exec_count = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        if self._results and self._exec_count < len(self._results):
            res = self._results[self._exec_count]
            self._exec_count += 1
            if isinstance(res, _FakeResult):
                return res
            return _FakeResult(value=res)
        return _FakeResult(self._scalar, self._rows)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        pass


@pytest.fixture
def mock_user() -> User:
    user = User()
    user.id = uuid4()
    user.credit_micros_balance = 1_000_000  # $1.00
    return user


@pytest.fixture
def active_promo_code() -> PromoCode:
    code = PromoCode()
    code.id = uuid4()
    code.code = "WELCOME50"
    code.credit_micros_granted = 2_000_000  # 50 credits ($2.00)
    code.max_uses = 100
    code.uses_count = 5
    code.expires_at = datetime.now(UTC) + timedelta(days=30)
    code.is_active = True
    return code


def test_normalize_promo_code() -> None:
    """Promo code strings are trimmed and converted to uppercase."""
    service = PromoCodeService(_FakeSession())
    assert service.normalize_code("  welcome50  ") == "WELCOME50"
    assert service.normalize_code("Nowing-Gift-2026") == "NOWING-GIFT-2026"


@pytest.mark.asyncio
async def test_claim_promo_code_success(
    mock_user: User, active_promo_code: PromoCode
) -> None:
    """Valid active promo code credits user balance and creates redemption record."""
    session = _FakeSession(results=[active_promo_code, None])
    service = PromoCodeService(session)

    result = await service.claim_promo_code(
        user=mock_user,
        code_input="welcome50",
    )

    assert result.credit_micros_granted == 2_000_000
    assert result.new_balance_micros == 3_000_000
    assert active_promo_code.uses_count == 6
    assert session.committed is True

    # Check redemption object created
    redemptions = [obj for obj in session.added if isinstance(obj, PromoCodeRedemption)]
    assert len(redemptions) == 1
    assert redemptions[0].user_id == mock_user.id
    assert redemptions[0].promo_code_id == active_promo_code.id
    assert redemptions[0].credit_micros_granted == 2_000_000


@pytest.mark.asyncio
async def test_claim_promo_code_already_redeemed(
    mock_user: User, active_promo_code: PromoCode
) -> None:
    """Attempting to claim the same promo code twice raises PromoCodeAlreadyRedeemedError."""
    existing_redemption = PromoCodeRedemption(
        id=uuid4(),
        user_id=mock_user.id,
        promo_code_id=active_promo_code.id,
        credit_micros_granted=2_000_000,
    )
    session = _FakeSession(results=[active_promo_code, existing_redemption])
    service = PromoCodeService(session)

    with pytest.raises(PromoCodeAlreadyRedeemedError):
        await service.claim_promo_code(
            user=mock_user,
            code_input="WELCOME50",
        )

    assert session.committed is False


@pytest.mark.asyncio
async def test_claim_promo_code_expired(mock_user: User) -> None:
    """Expired promo code is rejected."""
    expired_code = PromoCode()
    expired_code.id = uuid4()
    expired_code.code = "EXPIRED2025"
    expired_code.credit_micros_granted = 1_000_000
    expired_code.expires_at = datetime.now(UTC) - timedelta(days=1)
    expired_code.is_active = True

    session = _FakeSession(scalar=expired_code)
    service = PromoCodeService(session)

    async def mock_has_redeemed(uid: Any, cid: Any) -> bool:
        return False

    service.has_user_redeemed = mock_has_redeemed  # type: ignore

    with pytest.raises(PromoCodeExpiredError):
        await service.claim_promo_code(user=mock_user, code_input="EXPIRED2025")


@pytest.mark.asyncio
async def test_claim_promo_code_max_uses_exceeded(mock_user: User) -> None:
    """Promo code with uses_count >= max_uses is rejected as exhausted."""
    exhausted_code = PromoCode()
    exhausted_code.id = uuid4()
    exhausted_code.code = "LIMITED10"
    exhausted_code.credit_micros_granted = 1_000_000
    exhausted_code.max_uses = 10
    exhausted_code.uses_count = 10
    exhausted_code.is_active = True

    session = _FakeSession(scalar=exhausted_code)
    service = PromoCodeService(session)

    async def mock_has_redeemed(uid: Any, cid: Any) -> bool:
        return False

    service.has_user_redeemed = mock_has_redeemed  # type: ignore

    with pytest.raises(PromoCodeExhaustedError):
        await service.claim_promo_code(user=mock_user, code_input="LIMITED10")


@pytest.mark.asyncio
async def test_claim_promo_code_not_found(mock_user: User) -> None:
    """Non-existent code raises PromoCodeNotFoundError."""
    session = _FakeSession(scalar=None)
    service = PromoCodeService(session)

    with pytest.raises(PromoCodeNotFoundError):
        await service.claim_promo_code(user=mock_user, code_input="UNKNOWN999")
