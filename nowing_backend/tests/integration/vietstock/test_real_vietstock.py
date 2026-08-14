"""Real-network integration tests for the Vietstock scraper.

These tests hit the live Vietstock website and require outbound network.
They are skipped by default unless ``NOWING_RUN_NETWORK_TESTS`` is set.
"""

from __future__ import annotations

import os

import pytest

from app.proprietary.platforms.vietstock.fetch import (
    _set_cookie,
    fetch_financials,
    fetch_quote,
)
from app.proprietary.platforms.vietstock.parsers import parse_financials, parse_quote
from app.proprietary.platforms.vietstock.schemas import VietstockScrapeInput
from app.proprietary.platforms.vietstock.scraper import scrape_vietstock

pytestmark = pytest.mark.integration


def _should_run() -> bool:
    return os.environ.get("NOWING_RUN_NETWORK_TESTS") == "1" or os.environ.get(
        "CI"
    ) in {"1", "true"}


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    _set_cookie(None)
    monkeypatch.setattr(
        "app.proprietary.platforms.vietstock.fetch._last_request_at", None
    )
    monkeypatch.setattr(
        "app.proprietary.platforms.vietstock.fetch._verification_token", None
    )
    monkeypatch.setattr(
        "app.proprietary.platforms.vietstock.fetch._demo_mode", lambda: False
    )
    # Use the discovered real endpoints.
    monkeypatch.setattr(
        "app.config.config.VIETSTOCK_QUOTE_URL",
        "https://finance.vietstock.vn/company/tradinginfo",
    )
    monkeypatch.setattr(
        "app.config.config.VIETSTOCK_FINANCIAL_URL",
        "https://finance.vietstock.vn/data/financeinfo",
    )


@pytest.mark.skipif(not _should_run(), reason="network tests disabled")
async def test_fetch_and_parse_quote() -> None:
    """Real API: quote for VNM should parse with OHLC and ratios."""
    raw = await fetch_quote("VNM")
    quote = parse_quote(raw, "VNM")
    assert quote.symbol == "VNM"
    assert quote.current_price is not None
    assert quote.open_price is not None
    assert quote.high is not None
    assert quote.low is not None
    assert quote.close is not None
    assert quote.volume is not None
    assert quote.key_ratios is not None


@pytest.mark.skipif(not _should_run(), reason="network tests disabled")
async def test_fetch_and_parse_financials() -> None:
    """Real API: financials for VNM should parse with balance + income."""
    raw = await fetch_financials("VNM")
    financials = parse_financials(raw, "VNM")
    assert financials.symbol == "VNM"
    assert financials.balance_sheet.periods
    assert financials.income_statement.periods
    assert financials.balance_sheet.items
    assert financials.income_statement.items


@pytest.mark.skipif(not _should_run(), reason="network tests disabled")
async def test_scrape_vietstock_end_to_end() -> None:
    """Real API: full scrape should return non-degraded output."""
    inp = VietstockScrapeInput(symbol="VNM", include_financials=True)
    out = await scrape_vietstock(inp)
    assert out.quote is not None
    assert out.financials is not None
    assert not out.degraded
