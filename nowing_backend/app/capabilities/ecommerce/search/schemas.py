"""Schemas for ``ecommerce.search_products`` capability."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class EcommerceSearchInput(BaseModel):
    """Input payload for searching products on e-commerce platforms."""

    keyword: str = Field(..., min_length=1, description="Search keyword or product name")
    min_price: Decimal | None = Field(default=None, description="Minimum price filter in VND")
    max_price: Decimal | None = Field(default=None, description="Maximum price filter in VND")
    limit: int = Field(default=20, ge=1, le=100, description="Max number of items to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

    @property
    def estimated_units(self) -> int:
        return self.limit


class EcommerceProductItem(BaseModel):
    """Normalized e-commerce product summary."""

    item_id: int = Field(..., description="Shopee item ID")
    shop_id: int = Field(..., description="Shopee shop ID")
    title: str = Field(..., description="Product title")
    name: str | None = Field(default=None, description="Alias for title")
    brand: str | None = Field(default=None, description="Product brand")
    current_price: Decimal = Field(..., description="Current selling price in VND")
    original_price: Decimal | None = Field(default=None, description="Original list price")
    discount_percent: int = Field(default=0, description="Discount percentage")
    historical_sold: int = Field(default=0, description="Total units sold")
    rating_star: float = Field(default=0.0, description="Average review rating")
    rating_count: int = Field(default=0, description="Total review count")
    stock: int = Field(default=0, description="Available stock")
    status: str = Field(default="in_stock", description="in_stock, out_of_stock, unlisted")
    image_url: str | None = Field(default=None, description="Main image URL")
    product_url: str | None = Field(default=None, description="Canonical product URL")
    shop_name: str | None = Field(default=None, description="Merchant name")
    shop_location: str | None = Field(default=None, description="Shop location")
    raw_specs: dict[str, Any] = Field(default_factory=dict)


class EcommerceSearchOutput(BaseModel):
    """Output payload from e-commerce product search."""

    items: list[EcommerceProductItem] = Field(default_factory=list)
    total_count: int = Field(default=0)
    has_more: bool = Field(default=False)

    @property
    def billable_units(self) -> int:
        return len(self.items)
