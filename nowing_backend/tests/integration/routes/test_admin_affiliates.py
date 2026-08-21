"""Integration tests for Admin Affiliate Partner Payout Routes (Story 25.3 / ATDD Red Phase)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AffiliatePartner, AuditEvent, PartnerPayout, User


def _make_fake_redis_client():
    """Return an async Redis client double that always grants and releases the lock."""
    client = AsyncMock()
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    return client


@pytest.mark.integration
class TestAdminAffiliatesPayoutsRoutes:

    @pytest.mark.asyncio
    async def test_get_affiliate_payouts_list(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_user: User,
    ):
        """AC-1: GET /api/v1/admin/affiliates/payouts lists payout records with tax & partner info."""
        # Use an amount that converts to exactly 2,000,000 VND (above PIT threshold).
        amount_micros = 78_740_157  # ~$78.74 == 2,000,000 VND

        partner_id = uuid.uuid4()
        partner = AffiliatePartner(
            id=partner_id,
            user_id=db_user.id,
            referral_code=f"PARTNER_{uuid.uuid4().hex[:6].upper()}",
            partner_type="agency",
            balance_micros=amount_micros,
            hold_balance_micros=0,
            total_earned_micros=amount_micros,
            total_paid_micros=0,
            status="active",
        )
        db_session.add(partner)

        payout_id = uuid.uuid4()
        payout = PartnerPayout(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=amount_micros,
            status="pending",
            payout_details={
                "bank_bin": "970422",
                "bank_short_name": "MBBank",
                "account_number": "123456789",
                "account_holder": "NGUYEN VAN MINH",
                "risk_score": 15,
                "risk_level": "low",
            },
            created_at=datetime.now(UTC),
        )
        db_session.add(payout)
        await db_session.commit()

        res = await admin_client.get("/admin/affiliates/payouts?status=pending")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["total"] >= 1

        item = next(p for p in data["items"] if p["id"] == str(payout_id))
        # 2,000,000 VND gross, 10% PIT = 200,000 VND, net = 1,800,000 VND
        assert item["gross_amount_vnd"] == 2_000_000
        assert item["pit_tax_deduction_vnd"] == 200_000
        assert item["net_payout_amount_vnd"] == 1_800_000
        assert item["bank_short_name"] == "MBBank"
        assert item["account_holder"] == "NGUYEN VAN MINH"

    @pytest.mark.asyncio
    async def test_evaluate_payout_risk_endpoint(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_user: User,
    ):
        """AC-2: POST /api/v1/admin/affiliates/payouts/{payout_id}/evaluate calculates fraud risk."""
        partner_id = uuid.uuid4()
        partner = AffiliatePartner(
            id=partner_id,
            user_id=db_user.id,
            referral_code=f"PARTNER_{uuid.uuid4().hex[:6].upper()}",
            partner_type="agency",
            balance_micros=2_000_000_000,
            hold_balance_micros=2_000_000_000,
            status="active",
        )
        db_session.add(partner)

        payout_id = uuid.uuid4()
        payout = PartnerPayout(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=78_740_157,
            status="pending",
            payout_details={
                "bank_bin": "970422",
                "account_number": "111222333",
                "account_holder": "NGUYEN VAN MINH",
            },
            created_at=datetime.now(UTC),
        )
        db_session.add(payout)
        await db_session.commit()

        res = await admin_client.post(
            f"/admin/affiliates/payouts/{payout_id}/evaluate"
        )
        assert res.status_code == 200
        risk_data = res.json()
        assert "risk_score" in risk_data
        assert "risk_level" in risk_data
        assert "reasons" in risk_data

        # An evaluate audit event should be written.
        audit_query = select(AuditEvent).where(
            AuditEvent.action == "affiliate_payout_evaluate",
            AuditEvent.subject_id == db_user.id,
        )
        audit_res = await db_session.execute(audit_query)
        assert audit_res.scalars().first() is not None

    @pytest.mark.asyncio
    async def test_approve_affiliate_payout_with_audit(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_user: User,
    ):
        """AC-3 / INV-25.2: POST /api/v1/admin/affiliates/payouts/{id}/approve dispatches VietQR and logs audit."""
        amount_micros = 78_740_157

        partner_id = uuid.uuid4()
        partner = AffiliatePartner(
            id=partner_id,
            user_id=db_user.id,
            referral_code=f"PARTNER_{uuid.uuid4().hex[:6].upper()}",
            partner_type="agency",
            balance_micros=amount_micros,
            hold_balance_micros=0,
            status="active",
        )
        db_session.add(partner)

        payout_id = uuid.uuid4()
        payout = PartnerPayout(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=amount_micros,
            status="pending",
            payout_details={
                "bank_bin": "970422",
                "account_number": "333444555",
                "account_holder": "NGUYEN VAN MINH",
                "risk_score": 10,
                "risk_level": "low",
            },
            created_at=datetime.now(UTC),
        )
        db_session.add(payout)
        await db_session.commit()

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
            res = await admin_client.post(
                f"/admin/affiliates/payouts/{payout_id}/approve"
            )

        assert res.status_code == 200
        approve_data = res.json()
        assert approve_data["status"] == "processing"
        assert "tx_reference" in approve_data

        # Verify the gateway was actually called.
        mock_vietqr.return_value.initiate_payout.assert_called_once()

        # Verify AuditEvent recorded (INV-25.2)
        audit_query = select(AuditEvent).where(
            AuditEvent.action == "affiliate_payout_approve",
            AuditEvent.subject_id == db_user.id,
        )
        audit_res = await db_session.execute(audit_query)
        audit_event = audit_res.scalars().first()
        assert audit_event is not None

    @pytest.mark.asyncio
    async def test_reject_affiliate_payout_with_rollback(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_user: User,
    ):
        """AC-4: POST /api/v1/admin/affiliates/payouts/{id}/reject rolls back balance and logs reason."""
        amount_micros = 78_740_157

        partner_id = uuid.uuid4()
        partner = AffiliatePartner(
            id=partner_id,
            user_id=db_user.id,
            referral_code=f"PARTNER_{uuid.uuid4().hex[:6].upper()}",
            partner_type="agency",
            balance_micros=0,
            hold_balance_micros=amount_micros,
            status="active",
        )
        db_session.add(partner)

        payout_id = uuid.uuid4()
        payout = PartnerPayout(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=amount_micros,
            status="pending",
            payout_details={
                "bank_bin": "970422",
                "account_number": "777888999",
                "account_holder": "FRAUDSTER RING",
            },
            created_at=datetime.now(UTC),
        )
        db_session.add(payout)
        await db_session.commit()

        payload = {
            "rejection_reason": "suspected_fraud_ring",
            "notes": "Phát hiện tài khoản ảo tự referral theo cụm trong 1h",
        }
        res = await admin_client.post(
            f"/admin/affiliates/payouts/{payout_id}/reject",
            json=payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "rejected"
        assert data["rolled_back_balance_micros"] == amount_micros

        # Verify balance rolled back from hold_balance_micros -> balance_micros
        await db_session.refresh(partner)
        assert partner.balance_micros == amount_micros
        assert partner.hold_balance_micros == 0
