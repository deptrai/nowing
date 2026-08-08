"""``vietnamworks.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.config import config


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``vietnamworks.scrape``."""

    model_config = ConfigDict(extra="allow")

    keyword: str
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    employment_type: Literal["full_time", "contract", "part_time", "intern"] | None = None
    experience_years: int | None = None
    max_pages: int = Field(default=1, ge=0)
    max_items: int = Field(default=50, ge=0)

    @field_validator("max_items", mode="after")
    @classmethod
    def _clamp_max_items(cls, v: int) -> int:
        ceiling = getattr(config, "VIETNAMWORKS_MAX_ITEMS", 100)
        return min(v, ceiling)

    @field_validator("max_pages", mode="after")
    @classmethod
    def _clamp_max_pages(cls, v: int) -> int:
        ceiling = getattr(config, "VIETNAMWORKS_MAX_PAGES", 5)
        return min(v, ceiling)

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate."""
        return self.max_items


class ScrapeOutput(BaseModel):
    """Capability-level output for VietnamWorks job listings."""

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
