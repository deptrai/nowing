"""Pydantic schemas for multi-domain lead intelligence and company graph (Story 21.4)."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
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
        allowed = {
            "new",
            "open",
            "contacted",
            "qualified",
            "converted",
            "lost",
            "pending",
        }
        if cleaned not in allowed:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(allowed))}"
            )
        return cleaned


class LeadRead(BaseModel):
    """A lead record rendered in the Lead Intelligence Panel (Widget U3 & U4)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    client_id: str | None = None

    @field_validator("fit_score", "intent_score", "composite_score", mode="before")
    @classmethod
    def _validate_score_range(cls, v: Any) -> Any:
        if v is None:
            return v
        if not isinstance(v, float | int) or not math.isfinite(v):
            raise ValueError("Score must be a finite number")
        if v < 0 or v > 100:
            raise ValueError("Score must be between 0 and 100")
        return v

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
    stage_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    version: int = 1
    intent: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    price_estimate: str | None = None
    content_snippet: str | None = None
    author: str | None = None
    enriched: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    tax_id: str | None = None
    legal_representative: str | None = None
    charter_capital_vnd: int | None = None
    company_status: str | None = None
    is_zalo_active: bool = False
    contact_id: UUID | None = None
    is_unlocked: bool = False
    is_valid: bool | None = None
    consent_status: str | None = None


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

    @field_validator("confidence", mode="before")
    @classmethod
    def _validate_confidence(cls, v: Any) -> Any:
        if not isinstance(v, float | int) or not math.isfinite(v):
            raise ValueError("Confidence must be a finite number")
        if v < 0 or v > 1:
            raise ValueError("Confidence must be between 0 and 1")
        return v


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

    @field_validator("hiring_velocity_pct", mode="before")
    @classmethod
    def _validate_hiring_velocity(cls, v: Any) -> Any:
        if v is None:
            return v
        if not isinstance(v, float | int) or not math.isfinite(v):
            raise ValueError("Hiring velocity must be a finite number")
        return float(v)

    @field_validator("active_jobs_count", mode="before")
    @classmethod
    def _validate_active_jobs_count(cls, v: Any) -> Any:
        if v is None:
            return 0
        if not isinstance(v, int) or not math.isfinite(v):
            raise ValueError("Active jobs count must be a finite integer")
        if v < 0:
            raise ValueError("Active jobs count must be non-negative")
        return v


class PhoneResolutionRequest(BaseModel):
    """Payload for resolving a lead's phone via 3-tier waterfall."""

    source_url: str | None = None
    raw_text: str | None = None
    force_refresh: bool = False
    async_mode: bool = False


class PhoneResolutionResponse(BaseModel):
    """Result of 3-tier phone resolution waterfall."""

    lead_id: UUID
    phone_masked: str
    phone: str | None = None  # Populated only for authorized callers with CONTACTS_READ
    tier_reached: int
    provider_used: str
    status: str
    cost_credits: float = 1.5
    cost_micros: int = 1500000
    confidence: float = 0.95
    carrier: str = "Unknown"
    is_cached: bool = False
    contact_id: UUID | None = None
    degraded: bool = False
    degradation_reason: str | None = None
    task_id: str | None = None


class InvalidPhoneReportRequest(BaseModel):
    """Payload for reporting an invalid/dead phone number within 24h SLA."""

    reason: str = Field(
        default="reported_invalid_phone",
        description="Reason for reporting invalid phone",
    )


class PhoneRefundResponse(BaseModel):
    """Result of lead auto-refund processing."""

    lead_id: UUID
    refunded: bool
    refund_amount_credits: float
    refund_micros: int
    refunded_at: str
    status: str
    reason: str | None = None
    message: str


class BuyerPersona(BaseModel):
    """Target buyer persona extracted from website ICP analysis (Story 21.10)."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    industry: str
    company_size: str
    pain_points: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)


class FilterPresets(BaseModel):
    """Auto-configured Multi-Table filter presets (Story 21.10)."""

    model_config = ConfigDict(from_attributes=True)

    platforms: list[str] = Field(default_factory=list)
    intent: str = "BÁN"
    target_industries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    company_size_range: str | None = None


class ReverseIcpRequest(BaseModel):
    """Payload for 1-Click Reverse-ICP URL analysis."""

    url: str = Field(
        ..., max_length=2048, description="Target website, project, or landing page URL"
    )
    custom_instructions: str | None = Field(
        default=None, max_length=1000, description="Optional custom focus instructions"
    )


class ReverseIcpResponse(BaseModel):
    """Structured response for 1-Click Reverse-ICP (Story 21.10)."""

    model_config = ConfigDict(from_attributes=True)

    company_name: str
    domain: str
    value_proposition: str
    industry: str
    target_buyer_personas: list[BuyerPersona] = Field(default_factory=list)
    suggested_search_queries: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    filter_presets: FilterPresets = Field(default_factory=FilterPresets)
    chat_starter_prompts: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class EnrichmentDepth(StrEnum):
    """Depth of post-processing and enrichment applied to discovered leads."""

    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"


class BuyerIntent(StrEnum):
    """High-level buying intent classification for the target audience."""

    BUY = "buy"
    SELL = "sell"
    HIRE = "hire"
    PARTNER = "partner"
    INVEST = "invest"
    RENT = "rent"
    RESEARCH = "research"


class MultiSourceLeadGenRequest(BaseModel):
    """Payload for triggering unified multi-source lead generation (Story 21.15).

    P0 — Sales Copilot Loop: this schema doubles as the public surface for the
    6-phase Sales Copilot (discovery → smoke test → plan approval → execute →
    outreach → optimize).  Fields like ``smoke_test``, ``intent``,
    ``target_sources`` and ``campaign_id`` let the agent build a campaign spec
    without asking the user for repetition.
    """

    query: str = Field(
        ..., min_length=1, description="Natural language search description"
    )
    table_id: str | None = Field(
        default=None, description="Target table ID to stream results into"
    )
    locations: list[str] = Field(
        default_factory=list, description="Target locations or provinces"
    )
    limit: int = Field(
        default=50, ge=1, le=200, description="Maximum total leads to return"
    )

    # --- Sales Copilot campaign context ------------------------------------
    campaign_id: str | None = Field(
        default=None, description="Optional campaign ID for tracking / resume"
    )
    smoke_test: bool = Field(
        default=False,
        description="If true, run a low-cost preview before committing credits",
    )
    target_sources: list[str] = Field(
        default_factory=list,
        description="Explicit source adapters to query (e.g. batdongsan, topcv, masothue, social). If empty, auto-resolve from intent.",
    )
    target_keywords: list[str] = Field(
        default_factory=list,
        description="Positive keyword filters used for scoring and adapter selection"
    )
    negative_keywords: list[str] = Field(
        default_factory=list,
        description="Negative keywords that should disqualify a lead"
    )
    min_fit_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Minimum ICP fit score (0-100)"
    )
    enrichment_depth: EnrichmentDepth = Field(
        default=EnrichmentDepth.STANDARD,
        description="How aggressively to enrich and verify contact/company data"
    )
    intent: BuyerIntent | str = Field(
        default=BuyerIntent.BUY,
        description="High-level intent: buy, sell, hire, partner, invest, rent, research"
    )
    product_type: str | None = Field(
        default=None, description="Product or service being sold (e.g. SaaS, BĐS, recruitment)"
    )
    price_segment: str | None = Field(
        default=None, description="Price or budget segment (e.g. premium, mid-market, SMB)"
    )
    preferred_channels: list[str] = Field(
        default_factory=list,
        description="Outbound channels the user wants (e.g. email, phone, zalo, linkedin, facebook)"
    )

    @field_validator("intent", mode="before")
    @classmethod
    def _normalize_intent(cls, v: Any) -> str:
        if v is None:
            return BuyerIntent.BUY.value
        s = str(v).strip().lower()
        if not s:
            return BuyerIntent.BUY.value
        # Accept common Vietnamese / English synonyms & participles
        synonym_map: dict[str, str] = {
            "mua": "buy",
            "buying": "buy",
            "bán": "sell",
            "bán hàng": "sell",
            "selling": "sell",
            "tuyển dụng": "hire",
            "tuyển": "hire",
            "hiring": "hire",
            "hợp tác": "partner",
            "partnering": "partner",
            "đầu tư": "invest",
            "investing": "invest",
            "thuê": "rent",
            "cho thuê": "rent",
            "renting": "rent",
            "nghiên cứu": "research",
            "tìm hiểu": "research",
            "researching": "research",
        }
        mapped = synonym_map.get(s, s)
        allowed = {e.value for e in BuyerIntent}
        if mapped not in allowed:
            raise ValueError(f"intent must be one of {sorted(allowed)}, got {v!r}")
        return mapped


class MultiSourceLeadGenResponse(BaseModel):
    """Structured response for unified multi-source lead generation."""

    model_config = ConfigDict(from_attributes=True)

    status: str = "completed"
    total_discovered: int = 0
    total_deduplicated: int = 0
    leads: list[dict[str, Any]] = Field(default_factory=list)
    degraded_sources: list[str] = Field(default_factory=list)
    table_id: str | None = None


class LocationProfilePayload(BaseModel):
    """Pydantic model for customer location profile (Story 26.25 & 26.26)."""

    model_config = ConfigDict(extra="ignore")

    location_type: str = "both"
    province_code: str
    province_name: str
    district_codes: list[str] = Field(default_factory=list)
    district_names: list[str] = Field(default_factory=list)
    ward_codes: list[str] = Field(default_factory=list)
    ward_names: list[str] = Field(default_factory=list)
    location_text: str = ""

