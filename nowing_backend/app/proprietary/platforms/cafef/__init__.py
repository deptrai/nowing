"""CafeF stock/financials/news scraper (proprietary, BSL 1.1)."""

from __future__ import annotations

from .fetch import (
    CafeFAccessBlockedError,
    CafeFDecodeError,
    CafeFRateLimitedError,
    fetch_cafef,
    fetch_financials,
    fetch_news,
    fetch_quote,
)
from .parsers import parse_financials, parse_news, parse_quote
from .schemas import (
    CafeFFinancials,
    CafeFNewsItem,
    CafeFQuote,
    CafeFScrapeInput,
    CafeFScrapeOutput,
)
from .scraper import scrape_cafef

__all__ = [
    "CafeFAccessBlockedError",
    "CafeFDecodeError",
    "CafeFFinancials",
    "CafeFNewsItem",
    "CafeFQuote",
    "CafeFRateLimitedError",
    "CafeFScrapeInput",
    "CafeFScrapeOutput",
    "fetch_cafef",
    "fetch_financials",
    "fetch_news",
    "fetch_quote",
    "parse_financials",
    "parse_news",
    "parse_quote",
    "scrape_cafef",
]
