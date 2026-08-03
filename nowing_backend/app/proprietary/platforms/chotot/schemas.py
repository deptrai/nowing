# ruff: noqa: N815 - field names intentionally use the public camelCase API
"""Input/output models for the Chợ Tốt Nhà (nha.chotot.com) BĐS scraper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChototBdsScrapeInput(BaseModel):
    """Proprietary scraper input."""

    model_config = ConfigDict(extra="allow")

    listing_type: Literal["buy", "rent"] = "buy"
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
    def _price_bounds(self) -> ChototBdsScrapeInput:
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price cannot exceed max_price")
        if self.min_area is not None and self.max_area is not None and self.min_area > self.max_area:
            raise ValueError("min_area cannot exceed max_area")
        return self


class ChototBdsListing(BaseModel):
    """Single flat Chotot BĐS listing item."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["chotot_bds_listing"] = "chotot_bds_listing"
    listing_id: int | None = None
    ad_id: int | None = None
    title: str | None = None
    price: str | None = None
    price_raw: str | None = None
    price_value: int | None = None
    area: str | None = None
    area_raw: str | None = None
    area_value: float | None = None
    location: str | None = None
    district: str | None = None
    city: str | None = None
    ward: str | None = None
    post_date: str | None = None
    thumbnail_url: str | None = None
    detail_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    listing_type: str | None = None
    property_type: str | None = None
    seller_type: str | None = None
    rooms: int | None = None
    floors: int | None = None
    toilets: int | None = None
    scrapedAt: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to a flat dict for downstream consumers."""
        return self.model_dump(exclude_none=False)


class ChototBdsScrapeOutput(BaseModel):
    """Scraper-level output (not the capability contract)."""

    items: list[ChototBdsListing] = Field(default_factory=list)
    total_items: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def billable_units(self) -> int:
        """One returned listing = one billable unit."""
        return self.total_items
