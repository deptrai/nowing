"""``indeed.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``indeed.scrape``."""

    model_config = ConfigDict(extra="allow")

    keyword: str = Field(default="data engineer")
    location: str | None = Field(default="")
    salary_min: int | None = None
    salary_max: int | None = None
    employment_type: Literal["full_time", "contract", "part_time", "intern"] | None = (
        None
    )
    radius: int = Field(default=25, ge=0, le=100)
    sort: Literal["relevance", "date"] = Field(default="relevance")
    max_pages: int = Field(default=3, ge=0, le=5)
    max_items: int = Field(default=50, ge=0, le=100)

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate."""
        return self.max_items


class ScrapeOutput(BaseModel):
    """Capability-level output for Indeed job listings."""

    model_config = ConfigDict(extra="allow")

    items: list[dict[str, Any]] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None
    next_action: str | None = None

    @computed_field
    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        return len(self.items)
