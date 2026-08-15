"""``vietnamworks.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.config import config


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``vietnamworks.scrape``."""

    model_config = ConfigDict(extra="allow")

    keyword: str = Field(min_length=1)
    location: str | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    employment_type: Literal["full_time", "contract", "part_time", "intern"] | None = (
        None
    )
    experience_years: int | None = Field(default=None, ge=0)
    max_pages: int = Field(default=5, ge=0)
    max_items: int = Field(default=50, ge=0)

    @field_validator("keyword", mode="after")
    @classmethod
    def _strip_keyword(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("keyword must not be empty or whitespace")
        return v

    @field_validator("salary_min", "salary_max", "experience_years", mode="after")
    @classmethod
    def _non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("must be non-negative")
        return v

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

    @model_validator(mode="after")
    def _check_salary_range(self) -> ScrapeInput:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError("salary_max must be >= salary_min")
        return self

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
