"""``batdongsan.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``batdongsan.scrape``."""

    model_config = ConfigDict(extra="allow")

    listing_type: Literal["buy", "rent"] = "buy"
    city: str
    district_id: int | None = None
    max_pages: int = Field(default=5, ge=1, le=20)
    max_items: int = Field(default=10, ge=1, le=100)
    min_price: int | None = None
    max_price: int | None = None
    min_area: int | None = None
    max_area: int | None = None

    @model_validator(mode="after")
    def _price_and_area_bounds(self) -> "ScrapeInput":
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot be greater than max_price")
        if self.min_area is not None and self.max_area is not None:
            if self.min_area > self.max_area:
                raise ValueError("min_area cannot be greater than max_area")
        return self


class ScrapeOutput(BaseModel):
    """Capability-level output, extended by the proprietary ``to_output`` shape."""

    model_config = ConfigDict(extra="allow")

    items: list[dict[str, Any]] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @computed_field
    @property
    def total_items(self) -> int:
        return len(self.items)
