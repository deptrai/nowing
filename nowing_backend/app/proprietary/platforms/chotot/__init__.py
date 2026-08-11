"""Chợ Tốt multi-category scraper (proprietary, BSL 1.1)."""

from __future__ import annotations

from .fetch import (
    CategoryConfigError,
    ChototBdsAccessBlockedError,
    ChototBdsBotDetectedError,
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
    fetch_listings,
    fetch_phone,
    get_category_config,
    load_regions,
)
from .parsers import parse_listing, parse_listings
from .schemas import (
    ChototBdsListing,
    ChototBdsScrapeInput,
    ChototBdsScrapeOutput,
    ChototListing,
    ChototScrapeInput,
    ChototScrapeOutput,
)
from .scraper import scrape_chotot, scrape_chotot_bds

__all__ = [
    "CategoryConfigError",
    "ChototBdsAccessBlockedError",
    "ChototBdsBotDetectedError",
    "ChototBdsDecodeError",
    "ChototBdsListing",
    "ChototBdsRateLimitedError",
    "ChototBdsScrapeInput",
    "ChototBdsScrapeOutput",
    "ChototListing",
    "ChototScrapeInput",
    "ChototScrapeOutput",
    "fetch_listings",
    "fetch_phone",
    "get_category_config",
    "load_regions",
    "parse_listing",
    "parse_listings",
    "scrape_chotot",
    "scrape_chotot_bds",
]
