"""Pydantic schemas for multi-domain lead intelligence and company graph (Story 21.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadStatusUpdate(BaseModel):
    """Payload for updating CRM lead status."""

    status: str = Field(..., description="Lead pipeline status")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        cleaned = v.strip().lower()
        allowed = {"new", "open", "contacted", "qualified", "converted", "lost", "pending"}
        if cleaned not in allowed:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {', '.join(sorted(allowed))}")
        return cleaned


class LeadRead(BaseModel):
    """A lead record rendered in the Lead Intelligence Panel (Widget U3 & U4)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    client_id: str | None = None
    source: str
    source_url: str | None = None
    company_name: str
    domain: str | None = None
    industry: str | None = None
    company_size: str | None = None
    location: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    fit_score: float | None = None
    intent_score: float | None = None
    composite_score: float | None = None
    status: str = "new"
    intent: str | None = None
    phone: str | None = None
    price_estimate: str | None = None
    content_snippet: str | None = None
    author: str | None = None
    enriched: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


class LeadListResponse(BaseModel):
    """Paginated list of leads."""

    items: list[LeadRead]
    total: int
    limit: int
    offset: int


class DecisionMakerRead(BaseModel):
    """Decision maker associated with an enterprise (Widget U4 / Story 21.9)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    linkedin_url: str | None = None
    email: str | None = None
    phone: str | None = None
    confidence: float = 1.0


class TenderSummaryRead(BaseModel):
    """Active or historical public procurement tender (Widget U2 / Story 16.5)."""

    model_config = ConfigDict(from_attributes=True)

    tender_number: str
    title: str
    procuring_entity: str
    budget_vnd: float | None = None
    close_date: datetime | None = None
    source_url: str | None = None


class HiringSignalRead(BaseModel):
    """Hiring velocity signal from recruitment platforms (Widget U4 / Story 12.10)."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    department: str | None = None
    platform: str
    posted_date: datetime | None = None
    url: str | None = None


class LegalEntityRead(BaseModel):
    """Official enterprise registration details from dangkykinhdoanh / masothue."""

    model_config = ConfigDict(from_attributes=True)

    tax_id: str | None = None
    legal_name: str
    representative: str | None = None
    charter_capital: str | None = None
    founding_date: str | None = None
    headquarters: str | None = None
    status: str = "active"


class CompanyGraphRead(BaseModel):
    """Aggregated Company Graph showing decision makers, hiring, and tenders (Widget U4)."""

    model_config = ConfigDict(from_attributes=True)

    company_name: str
    legal_entity: LegalEntityRead | None = None
    decision_makers: list[DecisionMakerRead] = Field(default_factory=list)
    tenders: list[TenderSummaryRead] = Field(default_factory=list)
    hiring_signals: list[HiringSignalRead] = Field(default_factory=list)
    hiring_velocity_pct: float | None = None
    active_jobs_count: int = 0
