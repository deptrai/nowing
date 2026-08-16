"""Unit Tests for Story 23.3: Automated VietQR Affiliate Payout Reconciliation.

Governed by FR-91, INV-23.10, INV-23.11, and architecture-epic23-lead-infrastructure.md.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.partner_payout_service import PartnerPayoutService
from app.services.vietqr_payout_client import VietQRPayoutClient

pytestmark = [pytest.mark.unit]


class _FakeScalarResult:
    def __init__(self, value: Any = None):
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class TestDoubleEntryAndIdempotentLocking:
    """AC-1: Double-Entry Ledger & Idempotent Row-Locked Payout Execution."""

    @pytest.mark.asyncio
    async def test_execute_payout_acquires_row_lock_and_moves_to_hold(self):
        """Verify that execute_payout_with_lock acquires SELECT FOR UPDATE and transfers available to hold balance."""
        session = AsyncMock()
        payout_id = uuid.uuid4()
        partner_id = uuid.uuid4()

        mock_payout = MagicMock(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=50_000_000,  # $50
            status="pending",
            tx_reference=None,
            tax_code=None,
        )
        mock_partner = MagicMock(
            id=partner_id,
            balance_micros=100_000_000,
            hold_balance_micros=0,
        )

        session.execute.side_effect = [
            _FakeScalarResult(mock_payout),
            _FakeScalarResult(mock_partner),
        ]

        result = await PartnerPayoutService.execute_payout_with_lock(session, payout_id)

        assert result.status == "processing"
        assert result.tx_reference.startswith(f"NOWING-PAY-{payout_id}-")
        assert mock_partner.balance_micros == 50_000_000
        assert mock_partner.hold_balance_micros == 50_000_000

    @pytest.mark.asyncio
    async def test_execute_payout_fails_when_balance_insufficient(self):
        """Verify execute_payout_with_lock fails gracefully when available_balance < amount_micros."""
        session = AsyncMock()
        payout_id = uuid.uuid4()
        partner_id = uuid.uuid4()

        mock_payout = MagicMock(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=150_000_000,  # $150
            status="pending",
        )
        mock_partner = MagicMock(
            id=partner_id,
            balance_micros=50_000_000,  # only $50 available
            hold_balance_micros=0,
        )

        session.execute.side_effect = [
            _FakeScalarResult(mock_payout),
            _FakeScalarResult(mock_partner),
        ]

        with pytest.raises(HTTPException) as exc:
            await PartnerPayoutService.execute_payout_with_lock(session, payout_id)
        assert exc.value.status_code == 400


class TestPIT10PercentTaxCalculation:
    """AC-2: Thuế TNCN (PIT) 10% Automated Calculation (TT 111/2013/TT-BTC)."""

    def test_pit_tax_deduction_for_amounts_above_2m_vnd(self):
        """Payouts > 2,000,000 VNĐ (~$80 / 80_000_000 micros) must deduct 10% PIT tax."""
        amount_micros = 120_000_000  # $120 / 3,000,000 VNĐ
        tax_info = PartnerPayoutService.calculate_pit_tax(amount_micros)

        assert tax_info.tax_deducted_micros == 12_000_000
        assert tax_info.net_amount_micros == 108_000_000
        assert tax_info.tax_rate == 0.10
        assert tax_info.tax_exemption_applied is False
        assert tax_info.tax_code == "TNCN-10PCT-TT111"

    def test_pit_tax_exemption_for_amounts_under_2m_vnd(self):
        """Payouts < 2,000,000 VNĐ are exempt from immediate PIT deduction."""
        amount_micros = 60_000_000  # $60 / 1,500,000 VNĐ
        tax_info = PartnerPayoutService.calculate_pit_tax(amount_micros)

        assert tax_info.tax_deducted_micros == 0
        assert tax_info.net_amount_micros == 60_000_000
        assert tax_info.tax_exemption_applied is True
        assert tax_info.tax_code is None


class TestVietQRGatewayAndHMACReceipt:
    """AC-3: Bank Webhook Confirmation & Cryptographic HMAC Audit Receipt."""

    def test_hmac_sha256_webhook_signature_verification(self):
        """Verify HMAC-SHA256 signature verification rejects tampering and accepts valid payloads."""
        secret = "test_webhook_secret_key_123"
        payload = b'{"tx_reference":"NOWING-PAY-1-12345","status":"SUCCESS","napas_ref":"NAPAS999"}'
        valid_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        assert (
            VietQRPayoutClient.verify_webhook_signature(payload, valid_sig, secret)
            is True
        )
        assert (
            VietQRPayoutClient.verify_webhook_signature(payload, "invalid_sig", secret)
            is False
        )

    @pytest.mark.asyncio
    async def test_webhook_confirmation_finalizes_balances_and_creates_receipt(self):
        """Webhook SUCCESS callback deducts hold_balance, credits total_paid, sets status completed, generates HMAC receipt."""
        session = AsyncMock()
        payout_id = uuid.uuid4()
        partner_id = uuid.uuid4()

        mock_payout = MagicMock(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=80_000_000,
            tax_deducted_micros=0,
            net_amount_micros=80_000_000,
            tx_reference="NOWING-PAY-uuid-1700000000",
            status="processing",
            updated_at=None,
        )
        mock_partner = MagicMock(
            id=partner_id,
            hold_balance_micros=80_000_000,
            total_paid_micros=0,
        )

        session.execute.side_effect = [
            _FakeScalarResult(mock_payout),
            _FakeScalarResult(mock_partner),
        ]

        payload = {
            "tx_reference": "NOWING-PAY-uuid-1700000000",
            "status": "SUCCESS",
            "napas_ref": "NAPAS-2026-08-16-9999",
            "bank_code": "VCB",
            "account_no_masked": "******7890",
            "beneficiary_name": "NGUYEN VAN A",
        }

        receipt = await PartnerPayoutService.handle_webhook_confirmation(
            session, payload
        )

        assert receipt.status == "completed"
        assert receipt.napas_transaction_number == "NAPAS-2026-08-16-9999"
        assert receipt.hmac_audit_hash is not None
        assert mock_partner.hold_balance_micros == 0
        assert mock_partner.total_paid_micros == 80_000_000

    @pytest.mark.asyncio
    async def test_duplicate_failed_webhook_is_idempotent_no_infinite_refund(self):
        """Duplicate FAILED webhook callbacks must return idempotent receipt without double refunding."""
        session = AsyncMock()
        payout_id = uuid.uuid4()
        partner_id = uuid.uuid4()

        mock_payout = MagicMock(
            id=payout_id,
            partner_id=partner_id,
            amount_micros=50_000_000,
            tax_deducted_micros=0,
            net_amount_micros=50_000_000,
            tx_reference="NOWING-PAY-FAILED-123",
            status="failed",  # already failed
            napas_ref=None,
            hmac_audit_hash=None,
            updated_at=None,
        )

        session.execute.side_effect = [
            _FakeScalarResult(mock_payout),
        ]

        payload = {
            "tx_reference": "NOWING-PAY-FAILED-123",
            "status": "FAILED",
        }

        receipt = await PartnerPayoutService.handle_webhook_confirmation(
            session, payload
        )
        assert receipt.status == "failed"
        assert receipt.payout_id == payout_id


class TestTwoGeneralsTimeoutAutoReconciliation:
    """AC-4: Two-Generals Problem Timeout & Auto-Reconciliation Worker (INV-23.11)."""

    @pytest.mark.asyncio
    async def test_reconcile_worker_queries_gateway_status_on_timeout(self):
        """When payout is stuck in 'processing', worker queries GET /transfers/{tx_ref} without blind retries."""
        session = AsyncMock()
        client = AsyncMock()
        client.query_transfer_status.return_value = {
            "status": "SUCCESS",
            "napas_ref": "NAPAS-RESOLVED",
        }

        mock_partner = MagicMock(hold_balance_micros=50_000_000, total_paid_micros=0)
        payout = MagicMock(
            id=uuid.uuid4(),
            partner_id=uuid.uuid4(),
            status="processing",
            amount_micros=50_000_000,
            net_amount_micros=50_000_000,
            tax_deducted_micros=0,
            tx_reference="NOWING-PAY-1-123",
            partner=mock_partner,
        )

        session.execute.side_effect = [
            _FakeScalarResult(payout),
            _FakeScalarResult(mock_partner),
        ]

        await PartnerPayoutService.reconcile_payout_status(session, payout, client)

        # Asserts query_transfer_status was called (INV-23.11)
        client.query_transfer_status.assert_awaited_once_with("NOWING-PAY-1-123")
        assert payout.status == "completed"
        assert payout.hmac_audit_hash is not None
        assert mock_partner.hold_balance_micros == 0
        assert mock_partner.total_paid_micros == 50_000_000

    @pytest.mark.asyncio
    async def test_reconcile_worker_unlocks_funds_when_gateway_reports_failed(self):
        """When gateway reports FAILED, hold_balance is restored to available_balance and status marked failed."""
        session = AsyncMock()
        client = AsyncMock()
        client.query_transfer_status.return_value = {
            "status": "FAILED",
            "reason": "ACCOUNT_LOCKED",
        }

        partner = MagicMock(balance_micros=0, hold_balance_micros=50_000_000)
        payout = MagicMock(
            id=uuid.uuid4(),
            partner_id=uuid.uuid4(),
            status="processing",
            amount_micros=50_000_000,
            tx_reference="NOWING-PAY-1-123",
            partner=partner,
        )

        session.execute.side_effect = [
            _FakeScalarResult(payout),
            _FakeScalarResult(partner),
        ]

        await PartnerPayoutService.reconcile_payout_status(session, payout, client)

        assert payout.status == "failed"
        assert partner.hold_balance_micros == 0
        assert partner.balance_micros == 50_000_000
