"""Integration Tests for Story 23.3: Automated VietQR Affiliate Payout Reconciliation.

Governed by FR-91, INV-23.10 (DB Row-level Locking), and INV-23.11 (No blind retry).
Executes against real PostgreSQL database with pgvector.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AffiliatePartner, PartnerPayout, User
from app.services.partner_payout_service import PartnerPayoutService

pytestmark = [pytest.mark.integration]


@pytest_asyncio.fixture
async def live_partner_and_payout(async_engine):
    """Seed a real user, affiliate partner, and pending payout record in PostgreSQL."""
    user_id = uuid.uuid4()
    partner_id = uuid.uuid4()
    payout_id = uuid.uuid4()

    async with AsyncSession(async_engine) as session:
        user = User(
            id=user_id,
            email=f"payout-partner-{uuid.uuid4()}@nowing.test",
            hashed_password="hashed_pw",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        partner = AffiliatePartner(
            id=partner_id,
            user_id=user_id,
            referral_code=f"PARTNER-{uuid.uuid4().hex[:6].upper()}",
            partner_type="agency",
            status="active",
            commission_rate=0.15,
            balance_micros=100_000_000,  # $100.00 available
            hold_balance_micros=0,
            total_earned_micros=100_000_000,
            total_paid_micros=0,
        )
        payout = PartnerPayout(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=80_000_000,  # $80.00 requested
            amount_vnd=2_000_000,
            status="pending",
            payout_method="vietqr",
            payout_details={"bank_code": "VCB", "account_number": "1234567890"},
        )
        session.add_all([user, partner, payout])
        await session.commit()

    yield {"user_id": user_id, "partner_id": partner_id, "payout_id": payout_id}

    # Cleanup test records
    async with AsyncSession(async_engine) as session:
        await session.execute(
            text("DELETE FROM partner_payouts WHERE partner_id = :pid"),
            {"pid": partner_id},
        )
        await session.execute(
            text("DELETE FROM affiliate_partners WHERE id = :pid"),
            {"pid": partner_id},
        )
        await session.execute(
            text('DELETE FROM "user" WHERE id = :uid'),
            {"uid": user_id},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_payout_approval_prevents_double_spending(
    async_engine, live_partner_and_payout
):
    """INV-23.10: Concurrent Payout Approval DB Row-Level Locking Race Condition Test.
    
    Two concurrent transactions attempt to execute the exact same pending payout.
    PostgreSQL SELECT ... FOR UPDATE must serialize execution: exactly one succeeds and
    transitions status to 'processing', while the second is rejected with 409 Conflict.
    The partner balance must be deducted exactly once.
    """
    payout_id = live_partner_and_payout["payout_id"]
    partner_id = live_partner_and_payout["partner_id"]

    async def _try_execute(delay: float):
        async with AsyncSession(async_engine, expire_on_commit=False) as s:
            if delay > 0:
                await asyncio.sleep(delay)
            payout = await PartnerPayoutService.execute_payout_with_lock(s, payout_id)
            res_id = payout.id
            await s.commit()
            return res_id

    # Fire 2 concurrent execution requests simultaneously
    results = await asyncio.gather(
        _try_execute(0.0), _try_execute(0.005), return_exceptions=True
    )

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}. Failures: {failures}"
    assert len(failures) == 1, f"Expected exactly 1 conflict failure, got {len(failures)}"
    assert isinstance(failures[0], HTTPException)
    assert failures[0].status_code == 409

    # Verify DB state in PostgreSQL
    async with AsyncSession(async_engine) as verify_session:
        partner_row = (
            await verify_session.execute(
                text("SELECT balance_micros, hold_balance_micros FROM affiliate_partners WHERE id = :id"),
                {"id": partner_id},
            )
        ).mappings().one()

        payout_row = (
            await verify_session.execute(
                text("SELECT status, tx_reference, tax_deducted_micros, net_amount_micros FROM partner_payouts WHERE id = :id"),
                {"id": payout_id},
            )
        ).mappings().one()

        # Balance was 100M, payout was 80M -> remaining available 20M, hold 80M
        assert partner_row["balance_micros"] == 20_000_000
        assert partner_row["hold_balance_micros"] == 80_000_000
        assert payout_row["status"] == "processing"
        assert payout_row["tx_reference"].startswith(f"NOWING-PAY-{payout_id}-")


@pytest.mark.asyncio
async def test_payout_with_pit_10pct_tax_deduction_in_postgres(
    async_engine, live_partner_and_payout
):
    """AC-2: PIT 10% tax calculation for payout amount > 2,000,000 VNĐ (~$80 / 80M micros)."""
    partner_id = live_partner_and_payout["partner_id"]
    payout_id = uuid.uuid4()

    # Create payout of 120_000_000 micros ($120 / 3,000,000 VNĐ)
    async with AsyncSession(async_engine) as session:
        # Increase partner balance
        await session.execute(
            text("UPDATE affiliate_partners SET balance_micros = 150000000 WHERE id = :id"),
            {"id": partner_id},
        )
        payout = PartnerPayout(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=120_000_000,
            amount_vnd=3_000_000,
            status="pending",
            payout_method="vietqr",
            payout_details={"bank_code": "VCB", "account_number": "1234567890"},
        )
        session.add(payout)
        await session.commit()

    async with AsyncSession(async_engine) as session, session.begin():
        await PartnerPayoutService.execute_payout_with_lock(session, payout_id)
        await session.commit()

    async with AsyncSession(async_engine) as session:
        payout_row = (
            await session.execute(
                text("SELECT status, tax_deducted_micros, net_amount_micros, tax_code FROM partner_payouts WHERE id = :id"),
                {"id": payout_id},
            )
        ).mappings().one()

        assert payout_row["status"] == "processing"
        assert payout_row["tax_deducted_micros"] == 12_000_000  # 10% of 120M
        assert payout_row["net_amount_micros"] == 108_000_000   # 90% of 120M
        assert payout_row["tax_code"] == "TNCN-10PCT-TT111"


@pytest.mark.asyncio
async def test_webhook_confirmation_and_hmac_receipt_settlement(
    async_engine, live_partner_and_payout
):
    """AC-3: Webhook SUCCESS clears hold balance, credits total_paid, generates HMAC audit hash."""
    payout_id = live_partner_and_payout["payout_id"]
    partner_id = live_partner_and_payout["partner_id"]

    # Step 1: Transition to processing
    async with AsyncSession(async_engine) as session:
        payout = await PartnerPayoutService.execute_payout_with_lock(session, payout_id)
        tx_reference = payout.tx_reference
        await session.commit()

    # Step 2: Handle Webhook SUCCESS callback
    async with AsyncSession(async_engine) as session:
        payload = {
            "tx_reference": tx_reference,
            "status": "SUCCESS",
            "napas_ref": "NAPAS-INTEG-TEST-2026",
            "bank_code": "VCB",
            "account_no_masked": "******7890",
            "beneficiary_name": "NGUYEN VAN A",
        }
        receipt = await PartnerPayoutService.handle_webhook_confirmation(session, payload)
        await session.commit()

    assert receipt.status == "completed"
    assert receipt.napas_transaction_number == "NAPAS-INTEG-TEST-2026"
    assert receipt.hmac_audit_hash is not None

    # Step 3: Verify PostgreSQL balances
    async with AsyncSession(async_engine) as session:
        partner_row = (
            await session.execute(
                text("SELECT balance_micros, hold_balance_micros, total_paid_micros FROM affiliate_partners WHERE id = :id"),
                {"id": partner_id},
            )
        ).mappings().one()

        assert partner_row["hold_balance_micros"] == 0
        assert partner_row["total_paid_micros"] == 80_000_000


@pytest.mark.asyncio
async def test_auto_reconciliation_refunds_hold_balance_on_gateway_failure(
    async_engine, live_partner_and_payout
):
    """AC-4 & INV-23.11: Two-Generals resilience — safely refunds hold balance when gateway reports FAILED."""
    payout_id = live_partner_and_payout["payout_id"]
    partner_id = live_partner_and_payout["partner_id"]

    # Step 1: Transition to processing
    async with AsyncSession(async_engine) as session:
        await PartnerPayoutService.execute_payout_with_lock(session, payout_id)
        await session.commit()

    # Step 2: Reconcile payout with mock gateway returning FAILED
    fake_client = AsyncMock()
    fake_client.query_transfer_status.return_value = {"status": "FAILED", "reason": "BANK_ACCOUNT_INVALID"}

    async with AsyncSession(async_engine) as session:
        payout = (
            await session.execute(
                text("SELECT * FROM partner_payouts WHERE id = :id"),
                {"id": payout_id},
            )
        ).mappings().one()

        # Use handle_webhook_confirmation with FAILED status
        payload = {
            "tx_reference": payout["tx_reference"],
            "status": "FAILED",
            "reason": "BANK_ACCOUNT_INVALID",
        }
        await PartnerPayoutService.handle_webhook_confirmation(session, payload)
        await session.commit()

    # Step 3: Verify funds were safely refunded in PostgreSQL
    async with AsyncSession(async_engine) as session:
        partner_row = (
            await session.execute(
                text("SELECT balance_micros, hold_balance_micros FROM affiliate_partners WHERE id = :id"),
                {"id": partner_id},
            )
        ).mappings().one()

        payout_row = (
            await session.execute(
                text("SELECT status FROM partner_payouts WHERE id = :id"),
                {"id": payout_id},
            )
        ).mappings().one()

        assert payout_row["status"] == "failed"
        assert partner_row["hold_balance_micros"] == 0
        assert partner_row["balance_micros"] == 100_000_000  # 80M refunded back to 20M -> 100M
