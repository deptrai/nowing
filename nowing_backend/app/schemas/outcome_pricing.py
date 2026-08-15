"""Pydantic schemas for Outcome-Based Pricing (Story 21.7 / AD-42 / AD-48)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutcomeEventCreate(BaseModel):
    lead_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)
    attribution: str | None = None


class OutcomeEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    event_type: str
    lead_id: UUID
    sequence_id: UUID | None = None
    attribution: str
    cost_micros: int
    outcome_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PricingPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    plan_type: str
    seat_price: int | None = None
    outcome_rates_json: dict[str, int] = Field(default_factory=dict)
    billing_period: str | None = "monthly"
    is_active: bool = True


class PricingPlanUpdate(BaseModel):
    plan_type: Literal["seat", "outcome", "hybrid"] | None = None
    seat_price: int | None = Field(default=None, ge=0)
    outcome_rates_json: dict[str, int] | None = None
    billing_period: Literal["monthly", "annual"] | None = None

    @field_validator("outcome_rates_json")
    @classmethod
    def validate_rates(cls, v: dict[str, int] | None) -> dict[str, int] | None:
        if v is not None:
            for k, val in v.items():
                if val < 0:
                    raise ValueError(
                        f"Rate for outcome '{k}' must be non-negative (>= 0)."
                    )
        return v


class ServiceBreakdownItem(BaseModel):
    category: str
    total_tokens: int = 0
    cost_micros: int = 0
    event_count: int = 0


class ServiceBreakdownResponse(BaseModel):
    workspace_id: int
    start_date: datetime
    end_date: datetime
    items: list[ServiceBreakdownItem]
