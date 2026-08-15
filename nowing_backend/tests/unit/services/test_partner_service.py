"""Unit tests for PartnerService and 15% recurring commission engine (Story 21.18 / FR-88 / AD-42)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import HTTPException

from app.db import (
    AffiliatePartner,
    CreditPurchase,
    PartnerReferral,
    User,
)
from app.schemas.partner import (
    PartnerApplyRequest,
    PartnerPayoutRequest,
)
from app.services.partner_service import (
    USD_TO_VND_RATE,
    PartnerService,
    micros_to_usd,
    micros_to_vnd,
)

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value if self._value is not None else 0

    def scalar(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.flushed = False
        self._partner: AffiliatePartner | None = None
        self._referral: PartnerReferral | None = None
        self._user: User | None = None

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, statement: Any) -> _FakeResult:
        stmt_str = str(statement)
        if "FROM affiliate_partners" in stmt_str:
            return _FakeResult(value=self._partner)
        if "FROM partner_referrals" in stmt_str:
            return _FakeResult(value=self._referral)
        if 'FROM "user"' in stmt_str or "FROM user" in stmt_str:
            return _FakeResult(value=self._user)
        return _FakeResult()


@pytest.mark.asyncio
async def test_partner_service_helpers():
    assert micros_to_usd(20_000_000) == 20.0
    assert micros_to_vnd(1_000_000) == USD_TO_VND_RATE
    banks = PartnerService.get_supported_banks()
    assert len(banks) >= 10
    vcb = next(b for b in banks if b.code == "VCB")
    assert vcb.bin == "970436"


@pytest.mark.asyncio
async def test_apply_partner_success():
    session = _FakeAsyncSession()
    user_id = uuid.uuid4()
    req = PartnerApplyRequest(
        referral_code="growth-agency",
        partner_type="agency",
        payout_method="vietqr",
        payout_details={"bank_name": "Vietcombank", "account_number": "1234567890"},
    )

    partner = await PartnerService.apply_partner(session, user_id, req)

    assert partner.referral_code == "GROWTH-AGENCY"
    assert partner.partner_type == "agency"
    assert partner.commission_rate == 0.15
    assert partner.balance_micros == 0
    assert session.committed is True
    assert partner in session.added


@pytest.mark.asyncio
async def test_apply_partner_invalid_code():
    session = _FakeAsyncSession()
    user_id = uuid.uuid4()
    req = PartnerApplyRequest(referral_code="!@#")

    with pytest.raises(HTTPException) as exc:
        await PartnerService.apply_partner(session, user_id, req)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_record_referral_anti_self_referral():
    session = _FakeAsyncSession()
    user_id = uuid.uuid4()
    session._partner = AffiliatePartner(
        id=uuid.uuid4(),
        user_id=user_id,
        referral_code="TESTCODE",
        status="active",
    )

    # Attempting to refer themselves
    result = await PartnerService.record_referral(
        session, referred_user_id=user_id, referral_code="TESTCODE"
    )
    assert result is None
    assert len(session.added) == 0


@pytest.mark.asyncio
async def test_record_referral_success():
    session = _FakeAsyncSession()
    partner_user_id = uuid.uuid4()
    referred_user_id = uuid.uuid4()
    partner_id = uuid.uuid4()

    session._partner = AffiliatePartner(
        id=partner_id,
        user_id=partner_user_id,
        referral_code="TOPAGENCY",
        status="active",
    )

    result = await PartnerService.record_referral(
        session, referred_user_id=referred_user_id, referral_code="TOPAGENCY"
    )

    assert result is not None
    assert result.partner_id == partner_id
    assert result.referred_user_id == referred_user_id
    assert session.committed is True


@pytest.mark.asyncio
async def test_credit_commission_for_purchase_success():
    session = _FakeAsyncSession()
    partner_id = uuid.uuid4()
    buyer_user_id = uuid.uuid4()
    referral_id = uuid.uuid4()
    purchase_id = uuid.uuid4()

    session._referral = PartnerReferral(
        id=referral_id,
        partner_id=partner_id,
        referred_user_id=buyer_user_id,
    )
    session._partner = AffiliatePartner(
        id=partner_id,
        user_id=uuid.uuid4(),
        referral_code="VIPPARTNER",
        commission_rate=0.15,
        balance_micros=0,
        total_earned_micros=0,
        status="active",
    )

    purchase = CreditPurchase(
        id=purchase_id,
        user_id=buyer_user_id,
        quantity=100,
        credit_micros_granted=100_000_000,  # $100.00
        currency="USD",
        stripe_checkout_session_id="cs_test_123",
    )

    comm = await PartnerService.credit_commission_for_purchase(session, purchase)

    assert comm is not None
    assert comm.commission_micros == 15_000_000  # 15% of $100 = $15.00
    assert session._partner.balance_micros == 15_000_000
    assert session._partner.total_earned_micros == 15_000_000
    assert comm in session.added
    assert session.flushed is True


@pytest.mark.asyncio
async def test_request_payout_minimum_threshold():
    session = _FakeAsyncSession()
    user_id = uuid.uuid4()
    session._partner = AffiliatePartner(
        id=uuid.uuid4(),
        user_id=user_id,
        balance_micros=10_000_000,  # $10 (below $20 min)
        status="active",
    )

    req = PartnerPayoutRequest(amount_micros=10_000_000, payout_method="vietqr")

    with pytest.raises(HTTPException) as exc:
        await PartnerService.request_payout(session, user_id, req)
    assert exc.value.status_code == 400
    assert "Minimum payout" in exc.value.detail


@pytest.mark.asyncio
async def test_request_payout_vietqr_success():
    session = _FakeAsyncSession()
    user_id = uuid.uuid4()
    partner = AffiliatePartner(
        id=uuid.uuid4(),
        user_id=user_id,
        balance_micros=50_000_000,  # $50
        total_paid_micros=0,
        payout_method="vietqr",
        payout_details={"bank_name": "MBBank", "account_no": "99999999"},
        status="active",
    )
    session._partner = partner

    req = PartnerPayoutRequest(amount_micros=25_000_000, payout_method="vietqr")
    payout = await PartnerService.request_payout(session, user_id, req)

    assert payout.amount_micros == 25_000_000
    assert payout.amount_usd == 25.0
    assert payout.status == "pending"
    assert partner.balance_micros == 25_000_000
    assert partner.total_paid_micros == 25_000_000
    assert session.committed is True


@pytest.mark.asyncio
async def test_request_payout_credit_wallet_bonus():
    session = _FakeAsyncSession()
    user_id = uuid.uuid4()
    partner = AffiliatePartner(
        id=uuid.uuid4(),
        user_id=user_id,
        balance_micros=50_000_000,
        total_paid_micros=0,
        status="active",
    )
    user = User(
        id=user_id,
        email="partner@agency.com",
        credit_micros_balance=0,
    )
    session._partner = partner
    session._user = user

    req = PartnerPayoutRequest(amount_micros=20_000_000, payout_method="credit_wallet")
    payout = await PartnerService.request_payout(session, user_id, req)

    # 20_000_000 * 1.10 = 22_000_000 credit bonus
    assert user.credit_micros_balance == 22_000_000
    assert payout.status == "completed"
    assert partner.balance_micros == 30_000_000
    assert session.committed is True
