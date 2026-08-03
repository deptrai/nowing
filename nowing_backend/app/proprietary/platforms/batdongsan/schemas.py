# ruff: noqa: N815 - field names intentionally use the public camelCase API
"""Input/output models for the Batdongsan scraper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .city_codes import CITY_CODES


class BatdongsanScrapeInput(BaseModel):
    """Proprietary scraper input."""

    model_config = ConfigDict(extra="allow")

    listing_type: Literal["buy", "rent"] = "buy"
    city: str = "HN"
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
    def _clamp_caps(self) -> BatdongsanScrapeInput:
        # AC-3: over-cap values are clamped, not rejected; 0 is allowed.
        if self.max_items > 100:
            self.max_items = 100
        if self.max_pages > 20:
            self.max_pages = 20
        return self


class BatdongsanListing(BaseModel):
    """Single flat Batdongsan listing item."""

    model_config = ConfigDict(extra="allow")

    dataType: Literal["batdongsan_listing"] = "batdongsan_listing"
    listing_id: int | None = None
    title: str | None = None
    price: str | None = None
    price_raw: str | None = None
    area: str | None = None
    area_raw: str | None = None
    location: str | None = None
    district: str | None = None
    city: str | None = None
    post_date: str | None = None
    thumbnail_url: str | None = None
    detail_url: str | None = None
    phone: str | None = None
    phone_display: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    rooms: int | None = None
    scrapedAt: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to a flat dict for downstream consumers."""
        return self.model_dump(exclude_none=False)


class BatdongsanScrapeOutput(BaseModel):
    """Scraper-level output (not the capability contract)."""

    items: list[BatdongsanListing] = Field(default_factory=list)
    total_items: int = 0
    degraded: bool = False
    degradation_reason: str | None = None

    @property
    def billable_units(self) -> int:
        """One returned listing = one billable unit."""
        return self.total_items
