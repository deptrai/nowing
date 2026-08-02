# ruff: noqa: N815 - field names intentionally use the public camelCase API
"""Input/output models for the Batdongsan scraper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BatdongsanScrapeInput(BaseModel):
    """Proprietary scraper input."""

    model_config = ConfigDict(extra="allow")

    listing_type: Literal["buy", "rent"] = "buy"
    city: str = "HN"
    district_id: int | None = None
    max_pages: int = Field(default=5, ge=1, le=20)
    max_items: int = Field(default=10, ge=1, le=100)
    min_price: int | None = None
    max_price: int | None = None
    min_area: int | None = None
    max_area: int | None = None


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
