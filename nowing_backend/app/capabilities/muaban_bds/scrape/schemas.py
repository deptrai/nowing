"""Public input/output schemas for ``muaban_bds.scrape``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScrapeInput(BaseModel):
    """Input for the ``muaban_bds.scrape`` capability."""

    listing_type: Literal["buy", "rent"] = "buy"
    property_type: Literal["apartment", "house", "land", "office", "all"] = "all"
    city: str = Field(
        default="ho-chi-minh",
        description="City name or slug (e.g. ho-chi-minh, ha-noi).",
    )
    district: str | None = Field(
        default=None, description="Optional district name or slug."
    )
    max_pages: int = Field(default=5, ge=1, le=20)
    max_items: int = Field(default=10, ge=1, le=100)
    min_price: int | None = Field(default=None, description="Minimum price in VND.")
    max_price: int | None = Field(default=None, description="Maximum price in VND.")
    min_area: int | None = Field(default=None, description="Minimum area in m².")
    max_area: int | None = Field(default=None, description="Maximum area in m².")


class ScrapeOutput(BaseModel):
    """Output of the ``muaban_bds.scrape`` capability."""

    items: list[dict] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None
    next_action: str | None = None
