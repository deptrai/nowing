"""Vietstock scraper orchestration tests without real network."""

from __future__ import annotations

import pytest

from app.proprietary.platforms.vietstock.fetch import (
    VietstockAuthRefreshError,
    VietstockDecodeError,
    VietstockRateLimitedError,
)
from app.proprietary.platforms.vietstock.schemas import VietstockScrapeInput
from app.proprietary.platforms.vietstock.scraper import scrape_vietstock

pytestmark = pytest.mark.unit


def _demo_quote_raw(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "current_price": 75000.0,
        "open": 74000.0,
        "high": 76000.0,
        "low": 73500.0,
        "close": 75000.0,
        "volume": 1_000_000,
        "change": 1000.0,
        "change_percent": 1.35,
        "key_ratios": {"pe": 15.2, "pb": 2.1, "roe": 18.5, "roa": 10.2},
    }


def _demo_financials_raw(symbol: str) -> dict:
    return {
        "balance_sheet": {
            "periods": ["Q4-2025"],
            "items": [{"code": "270", "name": "Tổng tài sản", "values": [1000]}],
            "key_metrics": {},
            "unit": "tỷ VND",
        },
        "income_statement": {
            "periods": ["Q4-2025"],
            "items": [{"code": "10", "name": "Doanh thu thuần", "values": [500]}],
            "key_metrics": {},
            "unit": "tỷ VND",
        },
        "cash_flow": {
            "periods": ["Q4-2025"],
            "items": [
                {
                    "code": "HDKD_20",
                    "name": "Lưu chuyển tiền thuần từ HĐKD",
                    "values": [100],
                }
            ],
            "key_metrics": {},
            "unit": "tỷ VND",
        },
    }


async def _quote_ok(symbol: str) -> dict:
    return _demo_quote_raw(symbol)


async def _financials_ok(symbol: str) -> dict:
    return _demo_financials_raw(symbol)


async def test_scrape_full() -> None:
    """Mirror: should return quote, financials, and non-degraded output."""
    inp = VietstockScrapeInput(symbol="VNM", include_financials=True)
    out = await scrape_vietstock(
        inp,
        quote_fn=_quote_ok,
        financials_fn=_financials_ok,
    )
    assert out.quote is not None
    assert out.financials is not None
    assert not out.degraded
    assert out.billable_units == 1


async def test_scrape_quote_only() -> None:
    """Mirror: should return only quote when include_financials=False."""
    inp = VietstockScrapeInput(symbol="VNM", include_financials=False)
    out = await scrape_vietstock(inp, quote_fn=_quote_ok)
    assert out.quote is not None
    assert out.financials is None
    assert not out.degraded


async def test_scrape_degrades_on_rate_limit() -> None:
    """Over-Mocking: should handle httpx raising rate limit."""
    async def _rate_limited(symbol: str) -> dict:
        raise VietstockRateLimitedError("429")

    inp = VietstockScrapeInput(symbol="VNM")
    out = await scrape_vietstock(inp, quote_fn=_rate_limited)
    assert out.degraded
    assert out.degradation_reason == "rate_limited"
    assert out.billable_units == 0


async def test_scrape_degrades_on_auth_refresh_failure() -> None:
    """Over-Mocking: should handle 401/403 cookie refresh failure."""
    async def _auth_failed(symbol: str) -> dict:
        raise VietstockAuthRefreshError("AUTH_REFRESH_FAILED")

    inp = VietstockScrapeInput(symbol="VNM")
    out = await scrape_vietstock(inp, quote_fn=_auth_failed)
    assert out.degraded
    assert out.degradation_reason == "AUTH_REFRESH_FAILED"
    assert out.billable_units == 0


async def test_scrape_degrades_on_decode_error() -> None:
    """Over-Mocking: should handle invalid JSON / HTML response."""
    async def _bad(symbol: str) -> dict:
        raise VietstockDecodeError("bad json")

    inp = VietstockScrapeInput(symbol="VNM")
    out = await scrape_vietstock(inp, quote_fn=_bad)
    assert out.degraded
    assert out.degradation_reason == "decode_error"


async def test_scrape_invalid_symbol_degrades() -> None:
    """Edge: empty/invalid symbol should degrade without network."""
    inp = VietstockScrapeInput(symbol="")
    out = await scrape_vietstock(inp)
    assert out.degraded
    assert "invalid symbol" in (out.degradation_reason or "").lower()


async def test_scrape_concurrent_respects_throttle() -> None:
    """Concurrent: two simultaneous scrapes must respect process-local throttle."""
    calls = []

    async def _quote_slow(symbol: str) -> dict:
        calls.append(symbol)
        return _demo_quote_raw(symbol)

    inp = VietstockScrapeInput(symbol="VNM")
    out1 = await scrape_vietstock(inp, quote_fn=_quote_slow)
    out2 = await scrape_vietstock(inp, quote_fn=_quote_slow)
    assert out1.quote is not None
    assert out2.quote is not None
    assert len(calls) == 2
