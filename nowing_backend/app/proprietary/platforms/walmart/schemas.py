"""Input/output models for the Walmart scraper."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WalmartReviewItem(BaseModel):
    """One normalized Walmart review."""

    model_config = ConfigDict(extra="allow")

    text: str | None = None
    rating: float | None = None
    date: str | None = None
    verified: bool | None = None


class WalmartProductItem(BaseModel):
    """One normalized Walmart product."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    title: str | None = None
    price: float | None = None
    price_raw: str | None = None
    currency: str | None = None
    rating: float | None = None
    seller: str | None = None
    availability: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    review_summary: list[WalmartReviewItem] = Field(default_factory=list)
    source: str = "walmart"
    source_url: str | None = None
    is_active: bool = True

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat dict shape the scraper emits."""
        return self.model_dump()


class WalmartSearchInput(BaseModel):
    """Search-mode input for the Walmart product scraper."""

    model_config = ConfigDict(extra="allow")

    keyword: str
    page: int = Field(default=1, ge=1)
    max_items: int = Field(default=50, ge=1)


class WalmartScrapeInput(BaseModel):
    """Agent/REST input for the Walmart product scraper.

    Provide ``keyword`` for search mode or ``url`` for product mode.
    """

    model_config = ConfigDict(extra="allow")

    keyword: str | None = Field(default=None)
    url: str | None = Field(default=None)
    page: int = Field(default=1, ge=1)
    max_items: int = Field(default=50, ge=1)
    max_reviews: int = Field(default=5, ge=0)


class WalmartReviewsInput(BaseModel):
    """Input for the dedicated Walmart reviews scraper."""

    model_config = ConfigDict(extra="allow")

    url: str
    max_reviews: int = Field(default=100, ge=1)
