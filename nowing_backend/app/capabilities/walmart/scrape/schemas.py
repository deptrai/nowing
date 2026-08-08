"""``walmart.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``walmart.scrape``."""

    model_config = ConfigDict(extra="allow")

    keyword: str | None = Field(
        default=None,
        description="Search keyword, e.g. 'wireless earbuds'.",
    )
    url: str | None = Field(
        default=None,
        description="Product page URL containing /ip/ or /dp/.",
    )
    page: int = Field(default=1, ge=1, description="Search result page to start from.")
    max_items: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum product results to return.",
    )
    max_reviews: int = Field(
        default=5,
        ge=0,
        description="Maximum review summary items to attach per product page.",
    )

    @model_validator(mode="after")
    def _require_keyword_or_url(self) -> ScrapeInput:
        if not self.keyword and not self.url:
            raise ValueError("Provide either 'keyword' or 'url'.")
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable products for the pre-flight gate."""
        return self.max_items


class ScrapeOutput(BaseModel):
    """Capability-level output for Walmart product listings."""

    model_config = ConfigDict(extra="allow")

    items: list[dict[str, Any]] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None
    next_action: str | None = None

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        return len(self.items)
