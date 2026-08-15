"""Pydantic schemas for the Affiliate Partner program (Story 21.18 / FR-88 / AD-42)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PartnerApplyRequest(BaseModel):
    referral_code: str = Field(
        ...,
        min_length=3,
        max_length=32,
        description="Unique referral code (alphanumeric, e.g. 'GROWTHAGENCY')",
    )
    partner_type: str = Field(
        default="agency",
        description="Partner type: 'agency', 'freelancer', 'creator', 'enterprise_partner'",
    )
    payout_method: str = Field(
        default="vietqr",
        description="Preferred payout method: 'vietqr', 'credit_wallet', 'stripe'",
    )
    payout_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Bank details for VietQR or payout configuration",
    )


class PartnerPayoutSettingsUpdate(BaseModel):
    payout_method: str = Field(
        default="vietqr",
        description="Payout method: 'vietqr', 'credit_wallet', 'stripe'",
    )
    payout_details: dict[str, Any] = Field(
        ...,
        description="Bank name, account number, account holder name for VietQR",
    )


class PartnerProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    referral_code: str
    referral_url: str
    partner_type: str
    status: str
    commission_rate: float
    balance_micros: int
    balance_usd: float
    balance_vnd: int
    total_earned_micros: int
    total_earned_usd: float
    total_earned_vnd: int
    total_paid_micros: int
    payout_method: str
    payout_details: dict[str, Any]
    total_clicks: int = 0
    total_referrals: int = 0
    active_paying_referrals: int = 0
    created_at: datetime
    updated_at: datetime


class PartnerReferralItem(BaseModel):
    id: uuid.UUID
    referred_user_id: uuid.UUID
    masked_email: str
    attribution_source: str | None = None
    landing_page: str | None = None
    total_spent_micros: int = 0
    total_commission_micros: int = 0
    created_at: datetime


class PartnerReferralsListResponse(BaseModel):
    referrals: list[PartnerReferralItem]
    total_count: int


class PartnerCommissionItem(BaseModel):
    id: uuid.UUID
    referral_id: uuid.UUID
    credit_purchase_id: uuid.UUID | None = None
    source_amount_micros: int
    source_amount_usd: float
    commission_micros: int
    commission_usd: float
    commission_vnd: int
    commission_rate: float
    currency: str
    status: str
    created_at: datetime


class PartnerCommissionsListResponse(BaseModel):
    commissions: list[PartnerCommissionItem]
    total_count: int
    total_commission_micros: int


class PartnerPayoutRequest(BaseModel):
    amount_micros: int = Field(
        ...,
        gt=0,
        description="Amount to withdraw in micro-USD (e.g. 20_000_000 == $20.00)",
    )
    payout_method: str = Field(
        default="vietqr",
        description="'vietqr' or 'credit_wallet'",
    )
    payout_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional overrides for bank details or payout routing",
    )


class PartnerPayoutItem(BaseModel):
    id: uuid.UUID
    amount_micros: int
    amount_usd: float
    amount_vnd: int
    payout_method: str
    payout_details: dict[str, Any]
    status: str
    tx_reference: str | None = None
    requested_at: datetime
    processed_at: datetime | None = None
    created_at: datetime


class PartnerPayoutsListResponse(BaseModel):
    payouts: list[PartnerPayoutItem]
    total_count: int


class VietQrBankItem(BaseModel):
    bin: str
    name: str
    short_name: str
    code: str
