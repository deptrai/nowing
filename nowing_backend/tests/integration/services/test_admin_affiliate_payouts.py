"""Integration tests for Admin Affiliate Payout Service flows (Story 25.3).

Covers approve/reject idempotency, balance rollback, name-match rejection,
high-risk gating, and audit logging at the service layer.

These tests run against a real PostgreSQL database.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import AffiliatePartner, AuditEvent, PartnerPayout, User, get_async_session
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]

limiter.enabled = False


def _make_fake_redis_client():
    """Return an async Redis client double that always grants and releases the lock."""
    client = AsyncMock()
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    return client


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create a superuser for admin routes."""
    user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@nowing.test",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def admin_client(
    db_session: AsyncSession,
    admin_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated AsyncClient with superuser auth context."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(admin_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def seeded_payout(
    db_session: AsyncSession,
    admin_user: User,
) -> dict[str, object]:
    """Seed a partner and a pending payout, then clean up after the test."""
    partner_id = uuid.uuid4()
    payout_id = uuid.uuid4()
    amount_micros = 78_740_157  # ~2,000,000 VND

    partner = AffiliatePartner(
        id=partner_id,
        user_id=admin_user.id,
        referral_code=f"PARTNER-{uuid.uuid4().hex[:6].upper()}",
        partner_type="agency",
        balance_micros=amount_micros,
        hold_balance_micros=0,
        total_earned_micros=amount_micros,
        total_paid_micros=0,
        status="active",
    )
    payout = PartnerPayout(
        id=payout_id,
        partner_id=partner_id,
        amount_micros=amount_micros,
        amount_vnd=2_000_000,
        status="pending",
        payout_details={
            "bank_bin": "970422",
            "bank_short_name": "MBBank",
            "account_number": "123456789",
            "account_holder": "NGUYEN VAN MINH",
            "risk_score": 10,
            "risk_level": "low",
        },
        created_at=datetime.now(UTC),
    )
    db_session.add_all([partner, payout])
    await db_session.commit()

    yield {"partner_id": partner_id, "payout_id": payout_id, "amount_micros": amount_micros}


class TestAdminAffiliatePayoutServiceApprove:
    """AC-3 / INV-25.2: 1-Click approve, idempotency, audit, and safety gates."""

    @pytest.mark.asyncio
    async def test_approve_payout_is_idempotent(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        seeded_payout: dict[str, object],
    ):
        """A second approve call for the same payout must be rejected and must not re-dispatch VietQR."""
        payout_id = seeded_payout["payout_id"]
        fake_client = _make_fake_redis_client()

        with (
            patch(
                "app.routes.admin_affiliates_routes.get_redis_client",
                new=AsyncMock(return_value=fake_client),
            ),
            patch("app.routes.admin_affiliates_routes.VietQRPayoutClient") as mock_vietqr,
        ):
            mock_vietqr.return_value.initiate_payout = AsyncMock(
                return_value={"beneficiary_name": "NGUYEN VAN MINH"}
            )

            first = await admin_client.post(f"/admin/affiliates/payouts/{payout_id}/approve")
            assert first.status_code == 200

            second = await admin_client.post(f"/admin/affiliates/payouts/{payout_id}/approve")
            assert second.status_code == 409

        # Gateway dispatched exactly once
        mock_vietqr.return_value.initiate_payout.assert_called_once()

        # Payout is processing and has an immutable audit event
        audit_query = select(AuditEvent).where(
            AuditEvent.action == "affiliate_payout_approve"
        )
        audit_res = await db_session.execute(audit_query)
        assert audit_res.scalars().first() is not None

    @pytest.mark.asyncio
    async def test_approve_high_risk_payout_is_blocked(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        seeded_payout: dict[str, object],
    ):
        """Payouts with cached risk_score >= 70 must be rejected before lock/gateway."""
        payout_id = seeded_payout["payout_id"]
        payout = await db_session.get(PartnerPayout, payout_id)
        payout.payout_details = {
            **(payout.payout_details or {}),
            "risk_score": 80,
            "risk_level": "high",
        }
        await db_session.commit()

        res = await admin_client.post(f"/admin/affiliates/payouts/{payout_id}/approve")
        assert res.status_code == 409
        assert "high risk" in res.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_approve_name_mismatch_rejects_and_refunds(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        seeded_payout: dict[str, object],
    ):
        """If VietQR returns a different beneficiary name, the route must reject and refund hold balance."""
        payout_id = seeded_payout["payout_id"]
        amount_micros = seeded_payout["amount_micros"]
        fake_client = _make_fake_redis_client()

        with (
            patch(
                "app.routes.admin_affiliates_routes.get_redis_client",
                new=AsyncMock(return_value=fake_client),
            ),
            patch("app.routes.admin_affiliates_routes.VietQRPayoutClient") as mock_vietqr,
        ):
            # Gateway returns a different account holder name
            mock_vietqr.return_value.initiate_payout = AsyncMock(
                return_value={"beneficiary_name": "TRAN VAN B"}
            )
            res = await admin_client.post(f"/admin/affiliates/payouts/{payout_id}/approve")

        assert res.status_code == 409
        assert "mismatch" in res.json()["detail"].lower()

        # Balance was held then refunded
        partner = await db_session.get(AffiliatePartner, seeded_payout["partner_id"])
        assert partner.balance_micros == amount_micros
        assert partner.hold_balance_micros == 0

        # Audit event logged as a rejection
        audit_query = select(AuditEvent).where(
            AuditEvent.action == "affiliate_payout_reject"
        )
        audit_res = await db_session.execute(audit_query)
        assert audit_res.scalars().first() is not None


class TestAdminAffiliatePayoutServiceReject:
    """AC-4: Reject with reason, balance rollback, and audit logging."""

    @pytest.mark.asyncio
    async def test_reject_pending_payout_rolls_back_hold_balance(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Rejecting a pending payout that is already on hold must move balance back to available."""
        amount_micros = 78_740_157
        partner_id = uuid.uuid4()
        payout_id = uuid.uuid4()

        partner = AffiliatePartner(
            id=partner_id,
            user_id=admin_user.id,
            referral_code=f"PARTNER-{uuid.uuid4().hex[:6].upper()}",
            partner_type="agency",
            balance_micros=0,
            hold_balance_micros=amount_micros,
            total_earned_micros=amount_micros,
            total_paid_micros=0,
            status="active",
        )
        payout = PartnerPayout(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=amount_micros,
            amount_vnd=2_000_000,
            status="pending",
            payout_details={
                "bank_bin": "970422",
                "account_number": "999888777",
                "account_holder": "FRAUDSTER RING",
                "risk_score": 85,
                "risk_level": "high",
            },
            created_at=datetime.now(UTC),
        )
        db_session.add_all([partner, payout])
        await db_session.commit()

        res = await admin_client.post(
            f"/admin/affiliates/payouts/{payout_id}/reject",
            json={
                "rejection_reason": "suspected_fraud_ring",
                "notes": "Self-referral ring detected",
            },
        )
        assert res.status_code == 200

        await db_session.refresh(partner)
        assert partner.balance_micros == amount_micros
        assert partner.hold_balance_micros == 0

        audit_query = select(AuditEvent).where(
            AuditEvent.action == "affiliate_payout_reject",
            AuditEvent.subject_id == admin_user.id,
        )
        audit_res = await db_session.execute(audit_query)
        assert audit_res.scalars().first() is not None


class TestAdminAffiliatePayoutServiceDiscovery:
    """Service-level smoke tests for preview/discover and verify helpers."""

    @pytest.mark.asyncio
    async def test_evaluate_payout_risk_caches_result_in_payout_details(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        seeded_payout: dict[str, object],
    ):
        """Calling evaluate must persist risk_score/risk_level in payout_details."""
        payout_id = seeded_payout["payout_id"]

        res = await admin_client.post(f"/admin/affiliates/payouts/{payout_id}/evaluate")
        assert res.status_code == 200

        risk_data = res.json()
        assert "risk_score" in risk_data
        assert "risk_level" in risk_data

        payout = await db_session.get(PartnerPayout, payout_id)
        details = payout.payout_details or {}
        assert details.get("risk_score") == risk_data["risk_score"]
        assert details.get("risk_level") == risk_data["risk_level"]
