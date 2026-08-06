"""``walmart.reviews`` I/O contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewsInput(BaseModel):
    """MCP/agent-friendly surface for ``walmart.reviews``."""

    model_config = ConfigDict(extra="allow")

    url: str = Field(description="Product page URL containing /ip/ or /dp/.")
    max_reviews: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum reviews to return.",
    )

    @property
    def estimated_units(self) -> int:
        """Worst-case billable reviews for the pre-flight gate."""
        return self.max_reviews


class ReviewsOutput(BaseModel):
    """Capability-level output for Walmart product reviews."""

    model_config = ConfigDict(extra="allow")

    items: list[dict[str, Any]] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        return len(self.items)
