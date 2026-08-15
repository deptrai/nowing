"""Typed schemas for Shopee Vietnam scraper (Story 17.2 / AD-EC-1, AD-EC-2)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ShopeeProduct(BaseModel):
    """Normalized Shopee product data."""

    item_id: int = Field(..., description="Shopee item ID")
    shop_id: int = Field(..., description="Shopee shop ID")
    title: str = Field(..., description="Product title")
    name: str | None = Field(default=None, description="Alias for title")
    brand: str | None = Field(default=None, description="Product brand if available")
    current_price: Decimal = Field(..., description="Current selling price in VND (normalized)")
    original_price: Decimal | None = Field(
        default=None, description="Original list price before discount in VND"
    )
    discount_percent: int = Field(default=0, description="Discount percentage (0-100)")
    historical_sold: int = Field(default=0, description="Total all-time sold count")
    rating_star: float = Field(default=0.0, description="Average review rating (0.00 - 5.00)")
    rating_count: int = Field(default=0, description="Total number of reviews/ratings")
    stock: int = Field(default=0, description="Current available stock")
    status: str = Field(
        default="in_stock",
        description="Product availability status: in_stock, out_of_stock, unlisted",
    )
    image_url: str | None = Field(default=None, description="Main product image URL")
    product_url: str | None = Field(default=None, description="Canonical Shopee product URL")
    shop_name: str | None = Field(default=None, description="Merchant shop name")
    shop_location: str | None = Field(default=None, description="Merchant location / province")
    raw_specs: dict[str, Any] = Field(
        default_factory=dict, description="Raw specifications and metadata attributes"
    )

    def model_post_init(self, __context: Any) -> None:
        if self.name is None:
            self.name = self.title
        elif not self.title:
            self.title = self.name


class ShopeeSearchResponse(BaseModel):
    """Search response holding normalized products and pagination metadata."""

    items: list[ShopeeProduct] = Field(default_factory=list)
    total_count: int = Field(default=0)
    has_more: bool = Field(default=False)
