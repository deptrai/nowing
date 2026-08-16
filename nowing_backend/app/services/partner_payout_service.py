"""Partner Payout Reconciliation Engine & VietQR Gateway Service (Story 23.3 / FR-91 / INV-23.10 / INV-23.11)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AffiliatePartner, PartnerPayout
from app.services.partner_service import USD_TO_VND_RATE

# 2,000,000 VNĐ in USD micros threshold (TT 111/2013/TT-BTC)
# 2,000,000 / 25,000 = $80.00 -> 80_000_000 micros
PIT_TAX_THRESHOLD_MICROS = int((2_000_000 / USD_TO_VND_RATE) * 1_000_000)
PIT_TAX_RATE = 0.10
HMAC_RECEIPT_SECRET = os.environ.get("PAYOUT_HMAC_SECRET", "nowing_payout_audit_receipt_salt_2026")


@dataclass
class TaxCalculationResult:
    gross_amount_micros: int
    tax_deducted_micros: int
    net_amount_micros: int
    tax_rate: float
    tax_exemption_applied: bool


class PayoutReceipt(BaseModel):
    payout_id: uuid.UUID
    tx_reference: str
    status: str
    napas_transaction_number: str | None = None
    gross_amount_micros: int
    tax_deducted_micros: int
    net_amount_micros: int
    bank_code: str | None = None
    account_no_masked: str | None = None
    beneficiary_name: str | None = None
    hmac_audit_hash: str | None = None
    completed_at: datetime


class PartnerPayoutService:
    """Automated VietQR Payout Engine with Row-Level Locking, PIT deduction, and Two-Generals resilience."""

    @staticmethod
    def calculate_pit_tax(amount_micros: int) -> TaxCalculationResult:
        """Calculate 10% PIT (Thuế TNCN) deduction according to TT 111/2013/TT-BTC.
        
        Amounts > 2,000,000 VNĐ (~80,000,000 micros) are subject to 10% withholding.
        Amounts <= 2,000,000 VNĐ are exempt from deduction.
        """
        if amount_micros > PIT_TAX_THRESHOLD_MICROS:
            tax_deducted = int(amount_micros * PIT_TAX_RATE)
            net_amount = amount_micros - tax_deducted
            return TaxCalculationResult(
                gross_amount_micros=amount_micros,
                tax_deducted_micros=tax_deducted,
                net_amount_micros=net_amount,
                tax_rate=PIT_TAX_RATE,
                tax_exemption_applied=False,
            )
        else:
            return TaxCalculationResult(
                gross_amount_micros=amount_micros,
                tax_deducted_micros=0,
                net_amount_micros=amount_micros,
                tax_rate=0.0,
                tax_exemption_applied=True,
            )

    @classmethod
    async def execute_payout_with_lock(
        cls, session: AsyncSession, payout_id: uuid.UUID
    ) -> PartnerPayout:
        """Acquire explicit database row locks (INV-23.10) and transition funds to hold balance.
        
        BẮT BUỘC dùng SELECT ... FOR UPDATE trên partner_payouts và affiliate_partners.
        """
        # 1. Row-lock payout record
        stmt = (
            select(PartnerPayout)
            .where(PartnerPayout.id == payout_id)
            .with_for_update()
        )
        res = await session.execute(stmt)
        payout = res.scalar_one_or_none()

        if not payout:
            raise HTTPException(status_code=404, detail="Partner payout request not found")

        if payout.status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Payout {payout_id} is already in '{payout.status}' status (cannot execute)",
            )

        # 2. Row-lock partner account record
        partner_stmt = (
            select(AffiliatePartner)
            .where(AffiliatePartner.id == payout.partner_id)
            .with_for_update()
        )
        partner_res = await session.execute(partner_stmt)
        partner = partner_res.scalar_one_or_none()

        if not partner:
            raise HTTPException(status_code=404, detail="Affiliate partner record not found")

        if partner.balance_micros < payout.amount_micros:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient partner balance: available={partner.balance_micros}, required={payout.amount_micros}",
            )

        # 3. Calculate PIT 10% tax
        tax_info = cls.calculate_pit_tax(payout.amount_micros)
        payout.tax_deducted_micros = tax_info.tax_deducted_micros
        payout.net_amount_micros = tax_info.net_amount_micros
        if not tax_info.tax_exemption_applied and not payout.tax_code:
            payout.tax_code = "TNCN-10PCT-TT111"

        # 4. Double-entry balance transfer: available -> hold
        partner.balance_micros -= payout.amount_micros
        partner.hold_balance_micros += payout.amount_micros

        # 5. Generate idempotent transaction reference
        timestamp = int(time.time())
        payout.tx_reference = f"NOWING-PAY-{payout.id}-{timestamp}"
        payout.status = "processing"
        payout.processed_at = datetime.now(UTC)

        await session.flush()
        return payout

    @classmethod
    async def handle_webhook_confirmation(
        cls, session: AsyncSession, payload: dict[str, Any]
    ) -> PayoutReceipt:
        """Process gateway webhook callback and finalize balances (AC-3)."""
        tx_reference = payload.get("tx_reference")
        if not tx_reference:
            raise HTTPException(status_code=400, detail="Missing tx_reference in webhook payload")

        stmt = (
            select(PartnerPayout)
            .where(PartnerPayout.tx_reference == tx_reference)
            .with_for_update()
        )
        res = await session.execute(stmt)
        payout = res.scalar_one_or_none()

        if not payout:
            raise HTTPException(status_code=404, detail=f"Payout tx_reference {tx_reference} not found")

        # Idempotent return if already completed
        if payout.status == "completed":
            return PayoutReceipt(
                payout_id=payout.id,
                tx_reference=payout.tx_reference,
                status="completed",
                napas_transaction_number=payout.napas_ref,
                gross_amount_micros=payout.amount_micros,
                tax_deducted_micros=payout.tax_deducted_micros or 0,
                net_amount_micros=payout.net_amount_micros or payout.amount_micros,
                hmac_audit_hash=payout.hmac_audit_hash,
                completed_at=payout.updated_at or datetime.now(UTC),
            )

        partner_stmt = (
            select(AffiliatePartner)
            .where(AffiliatePartner.id == payout.partner_id)
            .with_for_update()
        )
        partner_res = await session.execute(partner_stmt)
        partner = partner_res.scalar_one_or_none()

        gateway_status = payload.get("status", "").upper()
        napas_ref = payload.get("napas_ref") or payload.get("napas_transaction_number")

        if gateway_status == "SUCCESS":
            if partner:
                partner.hold_balance_micros = max(0, partner.hold_balance_micros - payout.amount_micros)
                partner.total_paid_micros += payout.amount_micros

            payout.status = "completed"
            payout.napas_ref = napas_ref

            # Generate SHA256 HMAC cryptographic audit verification receipt
            raw_hmac_data = f"{payout.id}:{payout.tx_reference}:{napas_ref}:{payout.net_amount_micros}:{payout.tax_deducted_micros}"
            payout.hmac_audit_hash = hmac.new(
                HMAC_RECEIPT_SECRET.encode(),
                raw_hmac_data.encode(),
                hashlib.sha256,
            ).hexdigest()

        else:
            # Transfer failed at bank/gateway -> refund hold balance
            if partner:
                partner.hold_balance_micros = max(0, partner.hold_balance_micros - payout.amount_micros)
                partner.balance_micros += payout.amount_micros

            payout.status = "failed"

        await session.flush()

        return PayoutReceipt(
            payout_id=payout.id,
            tx_reference=payout.tx_reference,
            status=payout.status,
            napas_transaction_number=payout.napas_ref,
            gross_amount_micros=payout.amount_micros,
            tax_deducted_micros=payout.tax_deducted_micros or 0,
            net_amount_micros=payout.net_amount_micros or payout.amount_micros,
            bank_code=payload.get("bank_code"),
            account_no_masked=payload.get("account_no_masked"),
            beneficiary_name=payload.get("beneficiary_name"),
            hmac_audit_hash=payout.hmac_audit_hash,
            completed_at=datetime.now(UTC),
        )

    @classmethod
    async def reconcile_payout_status(
        cls, session: AsyncSession, payout: PartnerPayout, client: Any
    ) -> None:
        """Two-Generals reconciliation: queries gateway before modifying DB (INV-23.11)."""
        if not payout.tx_reference:
            return

        status_data = await client.query_transfer_status(payout.tx_reference)
        status = status_data.get("status", "").upper()

        if status == "SUCCESS":
            payout.status = "completed"
            payout.napas_ref = status_data.get("napas_ref")
            if hasattr(payout, "partner") and payout.partner:
                payout.partner.hold_balance_micros = max(0, payout.partner.hold_balance_micros - payout.amount_micros)
                payout.partner.total_paid_micros += payout.amount_micros
        elif status == "FAILED":
            payout.status = "failed"
            if hasattr(payout, "partner") and payout.partner:
                payout.partner.hold_balance_micros = max(0, payout.partner.hold_balance_micros - payout.amount_micros)
                payout.partner.balance_micros += payout.amount_micros
