"""Masothue.com company scraper (proprietary, BSL 1.1)."""

from __future__ import annotations

from .fetch import (
    MasothueAccessBlockedError,
    MasothueDecodeError,
    MasothueRateLimitedError,
    MasothueTimeoutError,
    fetch_detail_page,
    fetch_search_page,
)
from .parsers import apply_detail, parse_detail_table, parse_search_results
from .schemas import MasothueCompany, MasothueScrapeOutput, MasothueSearchInput
from .scraper import scrape_masothue

__all__ = [
    "MasothueAccessBlockedError",
    "MasothueCompany",
    "MasothueDecodeError",
    "MasothueRateLimitedError",
    "MasothueScrapeOutput",
    "MasothueSearchInput",
    "MasothueTimeoutError",
    "apply_detail",
    "fetch_detail_page",
    "fetch_search_page",
    "parse_detail_table",
    "parse_search_results",
    "scrape_masothue",
]
