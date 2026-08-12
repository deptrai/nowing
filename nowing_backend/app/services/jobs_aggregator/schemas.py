"""``jobs_aggregator`` Pydantic I/O contracts."""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field


class VnJobSalary(BaseModel):
    min: int | None = None
    max: int | None = None
    currency: str = "VND"
    period: Literal["month", "year", "hour", "negotiable", "hidden"] = "month"
    raw: str | None = None
    confidence: float = 0.0


class VnJobAggregatedListing(BaseModel):
    """A normalized, deduplicated job listing across VietnamWorks/TopCV/ITviec."""

    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    company: str
    location: str | None = None
    employment_type: str | None = None
    experience_years: int | None = None
    skills: list[str] = Field(default_factory=list)
    salary: VnJobSalary = Field(default_factory=VnJobSalary)
    posted_at: datetime.date | None = None
    job_description: str | None = None
    job_requirement: str | None = None
    source: Literal["vietnamworks", "topcv", "itviec", "multiple"]
    source_urls: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    salary_consistency_score: float = 0.0
    conflict: bool = False
    conflict_flags: list[str] = Field(default_factory=list)
    source_count: int = 1
    pii_redacted: bool = False

    _source_record_ids: dict[str, str] = PrivateAttr(default_factory=dict)
    _source_url_map: dict[str, str] = PrivateAttr(default_factory=dict)


class VnJobAggregateInput(BaseModel):
    """Input to the job market aggregator."""

    model_config = ConfigDict(extra="allow")

    keyword: str
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    employment_type: Literal["full_time", "contract", "part_time", "intern"] | None = (
        None
    )
    experience_years: int | None = None
    sources: list[Literal["vietnamworks", "topcv", "itviec"]] = Field(
        default_factory=lambda: ["vietnamworks", "topcv", "itviec"]
    )
    max_items_per_source: int = Field(default=50, ge=0, le=100)
    max_pages: int = Field(default=5, ge=0, le=20)

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate."""
        return self.max_items_per_source * len(self.sources)


class VnJobAggregateOutput(BaseModel):
    """Output of the job market aggregator."""

    model_config = ConfigDict(extra="allow")

    items: list[VnJobAggregatedListing] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list)
    degraded_source_ids: list[str] = Field(default_factory=list)
    source_breakdown: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 0.0
    salary_consistency_score: float = 0.0
    persistence_status: Literal["ok", "partial", "failed", "not_attempted"] = (
        "not_attempted"
    )
    persistence_message: str | None = None
    ingest_job_id: str | None = None

    @computed_field
    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        return self.total_items
