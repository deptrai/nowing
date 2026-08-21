"""Schemas for Admin Affiliate Partner Payout Desk & Anti-Fraud (Story 25.3)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PayoutStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"


class PayoutRejectionReason(StrEnum):
    NAME_MISMATCH = "name_mismatch"
    SUSPECTED_FRAUD_RING = "suspected_fraud_ring"
    INVALID_ACCOUNT = "invalid_account"


class AdminPayoutItem(BaseModel):
    id: str
    partner_id: str
    partner_name: str | None = None
    partner_email: str | None = None
    partner_code: str | None = None
    partner_tier: str = "standard"
    gross_amount_vnd: int
    pit_tax_deduction_vnd: int
    net_payout_amount_vnd: int
    bank_bin: str | None = None
    bank_short_name: str | None = None
    account_number: str | None = None
    account_holder: str | None = None
    name_match_status: str = "Unverified"
    risk_score: int = 10
    risk_level: str = "low"
    risk_reasons: list[str] = Field(default_factory=list)
    status: str
    tx_reference: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class AdminPayoutListResponse(BaseModel):
    items: list[AdminPayoutItem]
    total: int
    limit: int
    offset: int


class PayoutRiskResponse(BaseModel):
    payout_id: str
    risk_score: int
    risk_level: str
    reasons: list[str]
    evaluated_at: str


class PayoutApproveResponse(BaseModel):
    status: str
    payout_id: str
    tx_reference: str
    amount_micros: int
    net_amount_micros: int


class PayoutRejectRequest(BaseModel):
    rejection_reason: PayoutRejectionReason
    notes: str | None = None


class PayoutRejectResponse(BaseModel):
    status: str
    payout_id: str
    rejection_reason: str
    rolled_back_balance_micros: int
