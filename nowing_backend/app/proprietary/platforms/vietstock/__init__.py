"""Vietstock stock/financials scraper (proprietary, BSL 1.1)."""

from __future__ import annotations

from .fetch import (
    VietstockAccessBlockedError,
    VietstockAuthRefreshError,
    VietstockDecodeError,
    VietstockRateLimitedError,
    fetch_financials,
    fetch_quote,
    fetch_vietstock,
)
from .parsers import parse_financial_statement, parse_financials, parse_quote
from .schemas import (
    VietstockFinancialLineItem,
    VietstockFinancialReport,
    VietstockFinancials,
    VietstockKeyRatios,
    VietstockQuote,
    VietstockScrapeInput,
    VietstockScrapeOutput,
)
from .scraper import scrape_vietstock

__all__ = [
    "VietstockAccessBlockedError",
    "VietstockAuthRefreshError",
    "VietstockDecodeError",
    "VietstockFinancialLineItem",
    "VietstockFinancialReport",
    "VietstockFinancials",
    "VietstockKeyRatios",
    "VietstockQuote",
    "VietstockRateLimitedError",
    "VietstockScrapeInput",
    "VietstockScrapeOutput",
    "fetch_financials",
    "fetch_quote",
    "fetch_vietstock",
    "parse_financial_statement",
    "parse_financials",
    "parse_quote",
    "scrape_vietstock",
]
