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
    auto_unlock: bool = Field(default=False)


class SubTaskPlan(BaseModel):
    """Sub-task plan targeting a specific platform adapter."""

    model_config = ConfigDict(from_attributes=True)

    source_name: str
    query: str
    limit: int = 50
    filters: dict[str, Any] = Field(default_factory=dict)
    priority: int = 1


class SourcePlanAllocation(BaseModel):
    """Pre-flight source allocation with coverage and cost metadata."""

    model_config = ConfigDict(from_attributes=True)

    source_name: str
    category: str
    allocated_limit: int
    priority: int
    location_coverage_quality: str = "none"
    location_coverage_score: float = 0.0
    supported_provinces: list[str] = Field(default_factory=list)
    status: str = "ready"
    degraded_reason: str | None = None


class CampaignPlanResponse(BaseModel):
    """Enriched pre-flight plan breakdown for a campaign spec."""

    model_config = ConfigDict(from_attributes=True)

    campaign_name: str
    workspace_id: int
    total_planned_sources: int
    expected_sources: list[str]
    subtasks: list[SubTaskPlan]
    source_allocations: list[SourcePlanAllocation] = Field(default_factory=list)
    estimated_reachable_leads: int = 0
    estimated_cost_micros: int = 0
    estimated_cost_vnd: int = 0
    warnings: list[str] = Field(default_factory=list)


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


    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CampaignSpec":
        """Accept either a declarative CampaignSpec dict or a frontend CampaignCreateInput dict."""
        if "icp_config" in payload or "source_budget_config" in payload:
            return cls.from_campaign_create_input(payload)
        return cls.model_validate(payload)

    @classmethod
    def from_campaign_create_input(cls, payload: dict[str, Any]) -> "CampaignSpec":
        """Convert frontend CampaignCreateInput shape into internal CampaignSpec."""
        icp_config = payload.get("icp_config") or {}
        source_budget_config = payload.get("source_budget_config") or {}
        launch_config = payload.get("launch_config") or {}

        # Map ICP fields
        location_profile_raw = icp_config.get("location_profile")
        location_profile = None
        if location_profile_raw and isinstance(location_profile_raw, dict) and location_profile_raw.get("province_code"):
            from app.lead_intelligence.schemas import LocationProfilePayload
            p_code = location_profile_raw["province_code"]
            p_name = location_profile_raw.get("province_name") or p_code
            location_profile = LocationProfilePayload(
                province_code=p_code,
                province_name=p_name,
                district_codes=location_profile_raw.get("district_codes", []),
                district_names=location_profile_raw.get("district_names", []),
                ward_codes=location_profile_raw.get("ward_codes", []),
                ward_names=location_profile_raw.get("ward_names", []),
                street_name=location_profile_raw.get("street_name"),
                location_type=location_profile_raw.get("location_type", "both"),
            )

        keywords = icp_config.get("keywords") or icp_config.get("target_keywords") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        icp_criteria = ICPCriteria(
            target_industries=icp_config.get("target_industries", []),
            target_locations=icp_config.get("locations", []),
            target_company_sizes=icp_config.get("company_size_range") and [icp_config["company_size_range"]] or [],
            target_tech_stack=icp_config.get("tech_stack", []),
            target_keywords=keywords,
            negative_keywords=icp_config.get("negative_keywords", []),
            min_fit_score=source_budget_config.get("min_fit_score", 0.0),
            weights={},
            location_profile=location_profile,
        )

        # Map source budget list
        sources_list = [s for s in source_budget_config.get("sources", []) if s]
        total_target = int(source_budget_config.get("expected_leads_target", 50) or 50)
        num_sources = max(1, len(sources_list))
        per_source_target = min(1000, max(10, total_target // num_sources))

        budgets: list[SourceBudget] = []
        for src in sources_list:
            budgets.append(
                SourceBudget(
                    source_name=src,
                    max_leads=per_source_target,
                    priority=1,
                    auto_unlock=source_budget_config.get("auto_unlock_verified_phones", False),
                )
            )

        # Build effective query from ICP context
        query_parts: list[str] = []
        if icp_config.get("custom_instructions"):
            query_parts.append(icp_config["custom_instructions"])
        if icp_config.get("target_industries"):
            query_parts.extend(icp_config["target_industries"][:2])
        if icp_config.get("locations"):
            query_parts.extend(icp_config["locations"][:2])
        base_query = " ".join(query_parts) if query_parts else "Leads Campaign"

        return cls(
            name=payload.get("name", "Campaign"),
            workspace_id=payload.get("workspace_id", 1),
            query=base_query,
            icp_criteria=icp_criteria,
            intent_tags=icp_config.get("intents", []),
            source_budgets=budgets,
            target_sources=[s for s in source_budget_config.get("sources", [])],
            excluded_sources=[],
            max_total_leads=source_budget_config.get("expected_leads_target", 50),
            location_profile=location_profile,
            metadata={"launch_config": launch_config},
        )
