"""Shopee Vietnam scraping and price normalization package (Story 17.2)."""

from __future__ import annotations

from .models import EcommercePriceHistory, EcommerceProduct
from .normalizer import (
    SHOPEE_PRICE_SCALE,
    ShopeePriceNormalizer,
    extract_ids_from_url,
    normalize_discount,
    normalize_price,
    normalize_product_url,
    normalize_rating,
)
from .schemas import ShopeeProduct, ShopeeSearchResponse
from .scraper import (
    ShopeeBlockedError,
    ShopeeNotFoundError,
    ShopeeRateLimitedError,
    ShopeeScraper,
    ShopeeScraperError,
)

__all__ = [
    "SHOPEE_PRICE_SCALE",
    "EcommercePriceHistory",
    "EcommerceProduct",
    "ShopeeBlockedError",
    "ShopeeNotFoundError",
    "ShopeePriceNormalizer",
    "ShopeeProduct",
    "ShopeeRateLimitedError",
    "ShopeeScraper",
    "ShopeeScraperError",
    "ShopeeSearchResponse",
    "extract_ids_from_url",
    "normalize_discount",
    "normalize_price",
    "normalize_product_url",
    "normalize_rating",
]
