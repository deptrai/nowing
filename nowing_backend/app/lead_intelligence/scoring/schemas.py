"""Pydantic schemas for lead scoring (Story 21.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class IcpCriteria(BaseModel):
    """Ideal Customer Profile criteria for a workspace."""

    target_industries: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_company_sizes: dict[str, Any] = Field(default_factory=dict)
    target_tech_stack: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)


class LeadScoreInput(BaseModel):
    """Input to the lead-scoring capability."""

    lead_ids: list[UUID] | None = None
    recalculate_all: bool = False


class LeadScoreRead(BaseModel):
    """One scored lead returned by the engine."""

    id: UUID
    workspace_id: int
    client_id: str | None = None
    lead_id: UUID
    company_name: str
    score: float = Field(..., ge=0.0, le=100.0)
    fit_score: float = Field(..., ge=0.0, le=100.0)
    intent_score: float = Field(..., ge=0.0, le=100.0)
    classification: str
    factors_json: dict[str, Any] = Field(default_factory=dict)
    trend: str | None = None
    converted_similarity: float | None = None
    previous_score_id: UUID | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("classification")
    @classmethod
    def _validate_classification(cls, v: str) -> str:
        if v not in {"hot", "warm", "cold"}:
            raise ValueError("classification must be one of hot, warm, cold")
        return v


class LeadScoreOutput(BaseModel):
    """Output of the lead-scoring capability."""

    items: list[LeadScoreRead]
    cost_micros: int = 0
    degraded: bool = False
    degradation_reasons: list[str] | None = None
