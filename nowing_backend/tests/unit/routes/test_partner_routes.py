"""Unit tests for Affiliate Partner API routes (Story 21.18 / FR-88 / AD-42)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import (
    AffiliatePartner,
    get_async_session,
)
from app.routes.partner_routes import router
from app.users import require_session_context

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


class _FakeSession:
    def __init__(
        self,
        partner: AffiliatePartner | None = None,
        referrals: list[Any] | None = None,
        commissions: list[Any] | None = None,
        payouts: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = False
        self._partner = partner
        self._referrals = referrals or []
        self._commissions = commissions or []
        self._payouts = payouts or []

    def add(self, entity: Any) -> None:
        self.added.append(entity)
        if isinstance(entity, AffiliatePartner):
            self._partner = entity

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        pass

    async def refresh(self, entity: Any) -> None:
        if isinstance(entity, AffiliatePartner) and not getattr(entity, "id", None):
            entity.id = uuid.uuid4()
            entity.created_at = datetime.now(UTC)
            entity.updated_at = datetime.now(UTC)

    async def execute(self, statement: Any) -> _FakeResult:
        stmt_str = str(statement)
        if "count(partner_referrals.id)" in stmt_str:
            return _FakeResult(value=len(self._referrals))
        if (
            "count(DISTINCT partner_commissions.referral_id)" in stmt_str
            or "count(distinct" in stmt_str.lower()
        ):
            return _FakeResult(value=len(self._commissions))
        if "count(partner_commissions.id)" in stmt_str:
            return _FakeResult(value=len(self._commissions))
        if "count(partner_payouts.id)" in stmt_str:
            return _FakeResult(value=len(self._payouts))
        if "FROM affiliate_partners" in stmt_str:
            return _FakeResult(value=self._partner)
        if "FROM partner_referrals" in stmt_str:
            return _FakeResult(rows=self._referrals)
        if "FROM partner_commissions" in stmt_str:
            return _FakeResult(rows=self._commissions)
        if "FROM partner_payouts" in stmt_str:
            return _FakeResult(rows=self._payouts)
        return _FakeResult()


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_auth(test_user_id: uuid.UUID) -> AuthContext:
    user = SimpleNamespace(id=test_user_id, email="agency@nowing.net", is_active=True)
    return AuthContext.session(user=user)


@pytest.fixture
def test_app(fake_auth: AuthContext) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_session_context] = lambda: fake_auth
    return app


def test_get_supported_banks(test_app: FastAPI):
    client = TestClient(test_app)
    resp = client.get("/partners/supported-banks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(b["code"] == "VCB" for b in data)


def test_apply_partner_api(test_app: FastAPI, test_user_id: uuid.UUID):
    session = _FakeSession()
    test_app.dependency_overrides[get_async_session] = lambda: session
    client = TestClient(test_app)

    payload = {
        "referral_code": "VIETNAMGROWTH",
        "partner_type": "agency",
        "payout_method": "vietqr",
        "payout_details": {"bank": "MB", "account": "0987654321"},
    }
    resp = client.post("/partners/apply", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["referral_code"] == "VIETNAMGROWTH"
    assert data["commission_rate"] == 0.15
    assert "?ref=VIETNAMGROWTH" in data["referral_url"]


def test_get_partner_me(test_app: FastAPI, test_user_id: uuid.UUID):
    partner = AffiliatePartner(
        id=uuid.uuid4(),
        user_id=test_user_id,
        referral_code="AGENCY15",
        partner_type="agency",
        status="active",
        commission_rate=0.15,
        balance_micros=30_000_000,
        total_earned_micros=100_000_000,
        total_paid_micros=70_000_000,
        payout_method="vietqr",
        payout_details={"bank": "VCB"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session = _FakeSession(partner=partner)
    test_app.dependency_overrides[get_async_session] = lambda: session
    client = TestClient(test_app)

    resp = client.get("/partners/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["referral_code"] == "AGENCY15"
    assert data["balance_usd"] == 30.0
    assert data["total_earned_usd"] == 100.0


def test_payout_settings_update(test_app: FastAPI, test_user_id: uuid.UUID):
    partner = AffiliatePartner(
        id=uuid.uuid4(),
        user_id=test_user_id,
        referral_code="AGENCY15",
        partner_type="agency",
        status="active",
        commission_rate=0.15,
        balance_micros=30_000_000,
        total_earned_micros=100_000_000,
        total_paid_micros=0,
        payout_method="vietqr",
        payout_details={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session = _FakeSession(partner=partner)
    test_app.dependency_overrides[get_async_session] = lambda: session
    client = TestClient(test_app)

    payload = {
        "payout_method": "vietqr",
        "payout_details": {"bank_name": "Techcombank", "account_number": "1903333333"},
    }
    resp = client.put("/partners/payout-settings", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["payout_details"]["account_number"] == "1903333333"
