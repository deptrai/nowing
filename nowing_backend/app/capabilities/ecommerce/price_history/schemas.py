"""Schemas for ``ecommerce.track_price_history`` capability."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.capabilities.ecommerce.search.schemas import EcommerceProductItem


class PriceSnapshot(BaseModel):
    """Historical price data point."""

    price: Decimal = Field(..., description="Observed selling price in VND")
    recorded_at: str = Field(..., description="ISO 8601 timestamp of observation")


class EcommercePriceHistoryInput(BaseModel):
    """Input payload for tracking historical prices of an e-commerce product."""

    item_id: int | None = Field(default=None, description="Shopee item ID")
    shop_id: int | None = Field(default=None, description="Shopee shop ID")
    url: str | None = Field(default=None, description="Shopee product URL")
    external_product_id: str | None = Field(
        default=None, description="External platform product identifier"
    )

    @property
    def estimated_units(self) -> int:
        return 1


class EcommercePriceHistoryOutput(BaseModel):
    """Output containing current product specs and 90-day price history sparkline."""

    product: EcommerceProductItem = Field(..., description="Product current details")
    price_history: list[PriceSnapshot] = Field(
        default_factory=list, description="Historical price changes"
    )
    min_price: Decimal = Field(..., description="Lowest observed price in history")
    max_price: Decimal = Field(..., description="Highest observed price in history")
    current_price: Decimal = Field(..., description="Current normalized price")
    price_change_percentage_90d: float = Field(
        default=0.0, description="Percentage change in price over 90 days"
    )
    sparkline_points: list[Decimal] = Field(
        default_factory=list, description="Sequential price points for sparkline charts (Widget U1)"
    )

    @property
    def billable_units(self) -> int:
        return 1
