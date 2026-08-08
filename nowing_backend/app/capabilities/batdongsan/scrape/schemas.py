"""``batdongsan.scrape`` I/O contracts."""

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

from app.proprietary.platforms.batdongsan.city_codes import CITY_CODES


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``batdongsan.scrape``."""

    model_config = ConfigDict(extra="allow")

    listing_type: Literal["buy", "rent"] = "buy"
    city: str
    district_id: int | None = None
    max_pages: int = Field(default=5, ge=0)
    max_items: int = Field(default=10, ge=0)
    resolve_phones: bool = True
    min_price: int | None = None
    max_price: int | None = None
    min_area: int | None = None
    max_area: int | None = None

    @field_validator("city")
    @classmethod
    def _city_must_be_known(cls, value: str) -> str:
        if value not in CITY_CODES:
            raise ValueError(f"city must be one of {sorted(CITY_CODES)}")
        return value

    @model_validator(mode="after")
    def _clamp_caps(self) -> ScrapeInput:
        # AC-3: over-cap values are clamped, not rejected; 0 is allowed.
        if self.max_items > 100:
            self.max_items = 100
        if self.max_pages > 20:
            self.max_pages = 20
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate: ``max_items`` is a
        hard ceiling (le=100), so no single call can exceed it."""
        return self.max_items

    @model_validator(mode="after")
    def _price_and_area_bounds(self) -> ScrapeInput:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot be greater than max_price")
        if (
            self.min_area is not None
            and self.max_area is not None
            and self.min_area > self.max_area
        ):
            raise ValueError("min_area cannot be greater than max_area")
        return self


class ScrapeOutput(BaseModel):
    """Capability-level output, extended by the proprietary ``to_output`` shape."""

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
        """One returned listing = one billable unit."""
        return len(self.items)
