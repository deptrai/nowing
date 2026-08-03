"""Chotot BĐS scraper (proprietary, BSL 1.1)."""

from __future__ import annotations

from .fetch import (
    ChototBdsAccessBlockedError,
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
    fetch_listings,
    load_regions,
)
from .parsers import parse_listing, parse_listings
from .schemas import ChototBdsListing, ChototBdsScrapeInput, ChototBdsScrapeOutput
from .scraper import scrape_chotot_bds

__all__ = [
    "ChototBdsAccessBlockedError",
    "ChototBdsDecodeError",
    "ChototBdsListing",
    "ChototBdsRateLimitedError",
    "ChototBdsScrapeInput",
    "ChototBdsScrapeOutput",
    "fetch_listings",
    "load_regions",
    "parse_listing",
    "parse_listings",
    "scrape_chotot_bds",
]
