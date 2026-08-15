"""Pydantic schemas for contact enrichment (Story 21.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EnrichmentInput(BaseModel):
    """Input to the contact-enrichment capability."""

    lead_id: UUID | None = None
    lead_ids: list[UUID] | None = None
    requested_count: int = Field(default=5, ge=1, le=50)

    @field_validator("lead_ids")
    @classmethod
    def _validate_lead_ids(cls, v: list[UUID] | None) -> list[UUID] | None:
        if v is not None and len(v) > 200:
            raise ValueError("lead_ids must contain at most 200 leads")
        return v


class BulkEnrichmentInput(BaseModel):
    """Input to bulk contact enrichment across multiple leads (AC-8)."""

    lead_ids: list[UUID] = Field(min_length=1, max_length=200)
    requested_count: int = Field(default=5, ge=1, le=50)


class EnrichmentRequestRead(BaseModel):
    """One enrichment request surfaced to authorized callers."""

    id: UUID
    lead_id: UUID
    status: str
    contact_count: int = 0
    cost_micros: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"from_attributes": True}


class VerifiedContactRead(BaseModel):
    """A verified contact with decrypted PII for authorized callers."""

    id: UUID
    lead_id: UUID
    enrichment_request_id: UUID
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    verification_status: str = "unverified"
    confidence: float = 0.0
    source_provider: str = "fallback"
    consent_status: str | None = None
    legal_basis: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"from_attributes": True}


class EnrichmentOutput(BaseModel):
    """Output of the contact-enrichment capability (AC-9/AC-10)."""

    enrichment_request_id: UUID | None = None
    lead_id: UUID | None = None
    status: str = "pending"
    contact_count: int = 0
    cost_micros: int = 0
    verified_contact_ids: list[UUID] = Field(default_factory=list)
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list)


class EnrichmentCostOutput(BaseModel):
    """Cost projection for enriching a set of leads (AC-8)."""

    cost_per_contact_micros: int = 0
    estimated_cost_micros: int = 0
    lead_count: int = 0
