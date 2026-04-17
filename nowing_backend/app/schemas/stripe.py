"""Schemas for Stripe-backed subscriptions and token top-ups."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PlanId(str, Enum):
    """Supported subscription plan identifiers."""

    pro_monthly = "pro_monthly"
    pro_yearly = "pro_yearly"
    max_monthly = "max_monthly"
    max_yearly = "max_yearly"


class CreateTokenTopupRequest(BaseModel):
    """Request body for buying an LLM token top-up with a custom USD amount."""

    amount_usd: float = Field(gt=0, description="Amount in USD to spend on tokens (min $1).")
    search_space_id: int = Field(ge=1)


class CreateTokenTopupResponse(BaseModel):
    """Response containing the Stripe-hosted token top-up checkout URL."""

    checkout_url: str
    admin_approval_mode: bool = False


class CreateGiftCheckoutRequest(BaseModel):
    """Request body for creating a Stripe gift subscription checkout session."""

    plan_id: str = Field(description="Subscription plan to gift (e.g. 'pro_monthly').")
    duration_months: int = Field(ge=1, le=12, description="Gift duration in months.")


class CreateGiftCheckoutResponse(BaseModel):
    """Response containing the Stripe-hosted gift checkout URL."""

    checkout_url: str
    admin_approval_mode: bool = False


class RedeemGiftRequest(BaseModel):
    """Request body for redeeming a gift code."""

    model_config = {"str_strip_whitespace": True}

    code: str = Field(
        min_length=1,
        max_length=32,
        description="Gift code to redeem (e.g. GIFT-ABCD-EFGH-IJKL).",
    )


class RedeemGiftResponse(BaseModel):
    """Response after successfully redeeming a gift code."""

    new_expiry: datetime
    plan_id: str


class GiftCodeItem(BaseModel):
    """Single gift code entry in the history list."""

    id: uuid.UUID
    code: str
    plan_id: str
    duration_months: int
    status: str
    created_at: datetime
    expires_at: datetime
    redeemed_at: datetime | None = None


class GiftCodesResponse(BaseModel):
    """Response for GET /gift-codes."""

    items: list[GiftCodeItem]
    count: int


class RequestGiftRequest(BaseModel):
    """Request body for creating an admin-approval gift request."""

    plan_id: PlanId
    duration_months: Literal[1, 3, 6, 12]


class RequestGiftResponse(BaseModel):
    """Response after creating a gift request."""

    request_id: uuid.UUID
    message: str


class GiftRequestItem(BaseModel):
    """Single gift request entry in the admin list view."""

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    plan_id: str
    duration_months: int
    status: str
    gift_code_id: uuid.UUID | None = None
    gift_code: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class GiftRequestListResponse(BaseModel):
    """Response for GET /admin/gift-requests."""

    items: list[GiftRequestItem]
    count: int


class GiftRequestApproveResponse(BaseModel):
    """Response after admin approves a gift request."""

    request_id: uuid.UUID
    gift_code_id: uuid.UUID
    gift_code: str
    plan_id: str
    duration_months: int


class GiftRequestRejectRequest(BaseModel):
    """Request body for admin rejecting a gift request."""

    reason: str | None = Field(default=None, max_length=500)


class CreateSubscriptionCheckoutRequest(BaseModel):
    """Request body for creating a subscription checkout session."""

    plan_id: PlanId


class CreateSubscriptionCheckoutResponse(BaseModel):
    """Response containing the Stripe-hosted subscription checkout URL."""

    checkout_url: str
    admin_approval_mode: bool = False


class BillingPortalResponse(BaseModel):
    """Response containing the Stripe Customer Portal session URL."""

    url: str


class StripeStatusResponse(BaseModel):
    """Response describing Stripe availability."""

    stripe_enabled: bool


class StripeWebhookResponse(BaseModel):
    """Generic acknowledgement for Stripe webhook delivery."""

    received: bool = True
