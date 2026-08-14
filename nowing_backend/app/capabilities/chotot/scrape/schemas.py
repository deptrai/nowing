"""``chotot.scrape`` and ``chotot_bds.scrape`` I/O contracts."""

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

from app.proprietary.platforms.chotot.fetch import (
    CategoryConfigError,
    get_category_config,
)


class ScrapeInput(BaseModel):
    """MCP/agent-friendly surface for ``chotot.scrape``."""

    model_config = ConfigDict(extra="allow")

    category: str
    listing_type: Literal["buy", "rent", "sell", "want_to_buy"] = "sell"
    property_type: Literal["apartment", "house", "land", "office", "all"] = "all"
    city: str
    district: str | None = None
    district_id: int | None = Field(default=None, ge=0)
    max_pages: int = Field(default=5, ge=1, le=20)
    max_items: int = Field(default=10, ge=1, le=100)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    min_area: int | None = Field(default=None, ge=0)
    max_area: int | None = Field(default=None, ge=0)

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate."""
        return self.max_items

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        """Category must be a supported slug or a raw numeric gateway code."""
        try:
            get_category_config(value)
        except CategoryConfigError as exc:
            raise ValueError(f"category_not_supported: {value}") from exc
        return value

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


class ChototBdsScrapeInput(ScrapeInput):
    """Deprecated alias input — ``category`` defaults to ``bds``."""

    category: str = "bds"


class ScrapeOutput(BaseModel):
    """Capability-level output."""

    model_config = ConfigDict(extra="allow")

    items: list[dict[str, Any]] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None
    next_action: str | None = None
    category: str | None = None

    @computed_field
    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def billable_units(self) -> int:
        """One returned listing = one billable unit; unknown-category fallback listings are not billed."""
        return sum(
            1
            for item in self.items
            if isinstance(item, dict)
            and item.get("category")
            and item["category"] != "unknown"
        )
