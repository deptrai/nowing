# ruff: noqa: N815 - field names intentionally use the public camelCase API
"""Input/output models for the Chợ Tốt multi-category scraper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChototListing(BaseModel):
    """Single generic Chợ Tốt listing item."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["chotot_listing"] = "chotot_listing"
    listing_id: int | None = None
    ad_id: int | None = None
    title: str | None = None
    price: str | None = None
    price_raw: str | None = None
    price_value: int | None = None
    location: str | None = None
    district: str | None = None
    city: str | None = None
    ward: str | None = None
    post_date: str | None = None
    thumbnail_url: str | None = None
    detail_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    seller_type: str | None = None
    listing_type: str | None = None
    phone: str | None = None
    scrapedAt: str | None = None
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_output(self) -> dict[str, Any]:
        """Serialize to a flat dict for downstream consumers."""
        return self.model_dump(exclude_none=False)


class ChototBdsListing(ChototListing):
    """Deprecated BĐS-specific listing; kept for backward compatibility.

    New code should use ``ChototListing`` with ``category="bds"`` and
    BĐS-specific fields inside ``attributes``.
    """

    model_config = ConfigDict(extra="allow")

    dataType: Literal["chotot_bds_listing"] = "chotot_bds_listing"
    area: str | None = None
    area_raw: str | None = None
    area_value: float | None = None
    rooms: int | None = None
    floors: int | None = None
    toilets: int | None = None
    property_type: str | None = None

    @model_validator(mode="after")
    def _set_bds_category(self) -> ChototBdsListing:
        self.category = "bds"
        return self

    def to_output(self) -> dict[str, Any]:
        """Serialize to the legacy BĐS dict shape."""
        # Start from model_dump and keep BĐS-specific keys; suppress generic
        # attributes/category if they are empty so older consumers are not
        # surprised.
        out = super().to_output()
        if not out.get("attributes"):
            out.pop("attributes", None)
        return out


class ChototScrapeInput(BaseModel):
    """Proprietary multi-category scraper input."""

    model_config = ConfigDict(extra="allow")

    category: str
    listing_type: Literal["buy", "rent", "sell", "want_to_buy"] = "sell"
    property_type: Literal["apartment", "house", "land", "office", "all"] = "all"
    city: str = "hanoi"
    district: str | None = None
    district_id: int | None = Field(default=None, ge=0)
    max_pages: int = Field(default=5, ge=1, le=20)
    max_items: int = Field(default=10, ge=1, le=100)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    min_area: int | None = Field(default=None, ge=0)
    max_area: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _price_bounds(self) -> ChototScrapeInput:
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price cannot exceed max_price")
        if self.min_area is not None and self.max_area is not None and self.min_area > self.max_area:
            raise ValueError("min_area cannot exceed max_area")
        return self


class ChototBdsScrapeInput(ChototScrapeInput):
    """Deprecated BĐS input; ``listing_type`` uses old buy/rent literals."""

    category: str = "bds"
    listing_type: Literal["buy", "rent"] = "buy"

    @model_validator(mode="after")
    def _set_category(self) -> ChototBdsScrapeInput:
        self.category = "bds"
        # Map legacy listing_type to new semantics.
        return self


class ChototScrapeOutput(BaseModel):
    """Scraper-level output for the generic multi-category actor."""

    items: list[ChototListing] = Field(default_factory=list)
    total_items: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def billable_units(self) -> int:
        """Only successfully parsed, known-category listings are billable."""
        return sum(
            1 for item in self.items if item.category and item.category != "unknown"
        )


class ChototBdsScrapeOutput(ChototScrapeOutput):
    """Deprecated BĐS output; items are typed as the legacy BĐS listing."""

    items: list[ChototBdsListing] = Field(default_factory=list)
