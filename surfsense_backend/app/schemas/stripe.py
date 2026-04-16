"""Schemas for Stripe-backed subscriptions and token top-ups."""

from enum import Enum
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
