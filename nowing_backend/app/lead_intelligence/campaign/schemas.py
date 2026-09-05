"""Campaign Specification and Configuration Schemas (Story 21.15 / Signal-First Architecture)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.lead_intelligence.adapters.base import LeadSourceCategory
from app.lead_intelligence.schemas import LocationProfilePayload


class ScheduleFrequency(StrEnum):
    """Execution cadence for scheduled lead generation campaigns."""

    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ScheduleConfig(BaseModel):
    """Schedule and automation parameters for a recurring campaign."""

    model_config = ConfigDict(from_attributes=True)

    frequency: ScheduleFrequency = ScheduleFrequency.ONCE
    cron_expression: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_active: bool = True
    max_runs: int | None = None


class SourceBudget(BaseModel):
    """Source-specific budget allocation and limits."""

    model_config = ConfigDict(from_attributes=True)

    source_name: str
    max_leads: int = Field(default=50, ge=1, le=1000)
    priority: int = Field(default=1, ge=1, le=10)
    cost_limit_micros: int | None = None


class SubTaskPlan(BaseModel):
    """Sub-task plan targeting a specific platform adapter."""

    model_config = ConfigDict(from_attributes=True)

    source_name: str
    query: str
    limit: int = 50
    filters: dict[str, Any] = Field(default_factory=dict)
    priority: int = 1


class ICPCriteria(BaseModel):
    """Ideal Customer Profile criteria for targeting and relevance filtering."""

    model_config = ConfigDict(from_attributes=True)

    target_industries: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_company_sizes: list[str] = Field(default_factory=list)
    target_tech_stack: list[str] = Field(default_factory=list)
    target_categories: list[LeadSourceCategory] = Field(default_factory=list)
    target_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    min_fit_score: float = Field(default=0.0, ge=0.0, le=100.0)
    weights: dict[str, float] = Field(default_factory=dict)
    location_profile: LocationProfilePayload | None = None


class CampaignSpec(BaseModel):
    """Complete specification of a signal-first lead generation campaign."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Descriptive name of the campaign")
    workspace_id: int = Field(..., description="Target workspace ID")
    user_id: UUID | None = None
    client_id: str | None = None
    table_id: str | None = None

    # Targeting & Filtering
    query: str = Field(default="", description="Base search or natural language prompt")
    icp_criteria: ICPCriteria = Field(default_factory=ICPCriteria)
    intent_tags: list[str] = Field(
        default_factory=list,
        description="Buying intent tags: 'hiring', 'funding', 'tender', 'real_estate', 'expansion'",
    )
    signal_triggers: list[str] = Field(
        default_factory=list,
        description="Specific signal event types to monitor or match: 'funding', 'hiring', 'tech_stack', 'news'",
    )

    # Source & Execution Limits
    source_budgets: list[SourceBudget] = Field(default_factory=list)
    target_sources: list[str] = Field(
        default_factory=list,
        description="Explicit source adapters to include. If empty, dynamic resolution applies.",
    )
    excluded_sources: list[str] = Field(default_factory=list)
    max_total_leads: int = Field(default=100, ge=1, le=5000)
    concurrency_limit: int = Field(default=5, ge=1, le=20)
    adapter_timeout_seconds: float = Field(default=12.0, ge=1.0, le=60.0)

    location_profile: LocationProfilePayload | None = None

    # Schedule & Automation
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)
