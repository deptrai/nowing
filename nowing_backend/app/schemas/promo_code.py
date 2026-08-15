"""Pydantic schemas for Promo Code & Voucher Management (Story 21.7 / AC-5)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PromoCodeClaimRequest(BaseModel):
    code: str = Field(
        ..., min_length=3, max_length=50, description="Promo or voucher code string"
    )


class PromoCodeClaimResponse(BaseModel):
    code: str
    credit_micros_granted: int
    new_balance_micros: int
    message: str = "Promo code claimed successfully!"


class PromoCodeCreateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=50)
    credit_micros_granted: int = Field(
        ..., gt=0, description="Credits granted in micro-USD (1_000_000 = $1.00)"
    )
    max_uses: int | None = Field(default=None, gt=0)
    expires_at: datetime | None = None
    is_active: bool = True


class PromoCodeAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    credit_micros_granted: int
    max_uses: int | None = None
    uses_count: int = 0
    expires_at: datetime | None = None
    is_active: bool = True
    created_at: datetime
