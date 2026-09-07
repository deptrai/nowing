"""Pydantic schemas for Workspace Health & Adoption Analytics (Story 29.2, AD-52)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceHealthRange(StrEnum):
    RANGE_7D = "7d"
    RANGE_30D = "30d"
    RANGE_90D = "90d"
    RANGE_CUSTOM = "custom"


class MetricCardSummary(BaseModel):
    """Summary metrics with 14-day sparkline and 7-day change percentage."""

    model_config = ConfigDict(from_attributes=True)

    current_value: float | int | None = None
    change_pct: float | None = None
    sparkline: list[float | int] = Field(default_factory=list)


class TopSourceItem(BaseModel):
    """Ranked usage and cost per knowledge/scraper source."""

    model_config = ConfigDict(from_attributes=True)

    source_type: str
    memory_count: int = 0
    query_count: int = 0
    cost_micros: int | None = None


class CoverageGapItem(BaseModel):
    """Enabled source with zero memories in trailing 30 days."""

    model_config = ConfigDict(from_attributes=True)

    source_type: str
    enabled_since: datetime | str
    last_synced_at: datetime | str | None = None
    remediation_action: str
    configure_url: str


class CoverageGapsResponse(BaseModel):
    """Response containing list of detected coverage gaps."""

    model_config = ConfigDict(from_attributes=True)

    gaps: list[CoverageGapItem] = Field(default_factory=list)
    total_gaps: int = 0


class QuotaProgressItem(BaseModel):
    """Progress towards workspace quota with advisory status."""

    model_config = ConfigDict(from_attributes=True)

    metric: str
    label: str
    current_value: int
    limit_value: int | None = None
    utilization_pct: float | None = None
    status: str = "normal"  # normal (<80%), warning (80-99%), alert (>=100%)
    recommended_tier: str | None = None


class WorkspaceHealthDailyPoint(BaseModel):
    """Single-day health metric point for time-series charts."""

    model_config = ConfigDict(from_attributes=True)

    date: str
    active_members_dau: int | None = None
    active_members_wau: int | None = None
    total_members: int = 0
    total_memories: int = 0
    memory_growth_count: int = 0
    recall_queries: int = 0
    remember_queries: int = 0
    research_queries: int = 0
    query_volume: int = 0
    credits_consumed_micros: int | None = None
    cost_per_turn_micros: int | None = None


class WorkspaceHealthSummaryResponse(BaseModel):
    """Full health analytics response payload with live overlay and sparklines."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: int
    date_range: str
    start_date: str
    end_date: str
    is_public_snapshot: bool = False

    # Top metric cards (HD-1)
    total_members: MetricCardSummary
    active_members_dau: MetricCardSummary | None = None
    active_members_wau: MetricCardSummary | None = None
    total_memories: MetricCardSummary
    memory_growth_count: MetricCardSummary
    query_volume: MetricCardSummary
    credits_consumed_micros: MetricCardSummary | None = None
    cost_per_turn_micros: MetricCardSummary | None = None

    # Query breakdowns
    recall_queries: int = 0
    remember_queries: int = 0
    research_queries: int = 0

    # Top sources & Gaps
    top_sources: list[TopSourceItem] = Field(default_factory=list)
    source_coverage_gap_count: int = 0

    # Quota Progress (HD-2)
    quota_progress: list[QuotaProgressItem] | None = None

    # Daily Time-Series
    daily_metrics: list[WorkspaceHealthDailyPoint] = Field(default_factory=list)


class SourceTimelineSample(BaseModel):
    """Sample memory item in source drilldown timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime | str
    confidence: float = 1.0
    tags: list[str] = Field(default_factory=list)


class SourceBreakdownResponse(BaseModel):
    """Source drilldown response with volume, cost attribution, and samples (HD-5)."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: int
    source_type: str
    total_memories: int = 0
    query_volume: int = 0
    cost_micros: int | None = None
    recent_samples: list[SourceTimelineSample] = Field(default_factory=list)
