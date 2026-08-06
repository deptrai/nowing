"""Scraper orchestration tests without real network."""

from __future__ import annotations

from app.proprietary.platforms.cafef.fetch import (
    CafeFDecodeError,
    CafeFRateLimitedError,
)
from app.proprietary.platforms.cafef.schemas import CafeFScrapeInput
from app.proprietary.platforms.cafef.scraper import scrape_cafef


def _demo_quote_raw(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "current_price": 80.5,
        "open_price": 79.0,
        "high": 81.0,
        "low": 78.5,
        "close": 80.0,
        "volume": 1_000_000,
        "change": 0.5,
        "change_percent": 0.63,
        "timestamp": "2026-01-01",
        "key_ratios": {"pe": 12.0},
    }


def _demo_financials_raw(symbol: str) -> dict:
    return {
        "balance_sheet": {
            "periods": ["Q1-2026"],
            "items": [
                {"code": "270", "name": "Tổng tài sản", "values": [1000]}
            ],
            "key_metrics": {},
            "unit": "tỷ VND",
        },
        "income_statement": {
            "periods": ["Q1-2026"],
            "items": [
                {"code": "10", "name": "Doanh thu thuần", "values": [500]}
            ],
            "key_metrics": {},
            "unit": "tỷ VND",
        },
        "cash_flow": {
            "periods": ["Q1-2026"],
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


def _demo_news_raw(symbol: str, max_news: int) -> list[dict]:
    return [
        {
            "title": f"{symbol} news {i}",
            "url": f"https://cafef.vn/{symbol}-{i}.chn",
            "published_at": "2026-01-01",
            "summary": "summary",
        }
        for i in range(max_news)
    ]


async def _quote_ok(symbol: str) -> dict:
    return _demo_quote_raw(symbol)


async def _financials_ok(symbol: str) -> dict:
    return _demo_financials_raw(symbol)


async def _news_ok(symbol: str, max_news: int) -> list[dict]:
    return _demo_news_raw(symbol, max_news)


async def test_scrape_full() -> None:
    inp = CafeFScrapeInput(symbol="VCB", include_financials=True, include_news=True)
    out = await scrape_cafef(
        inp,
        quote_fn=_quote_ok,
        financials_fn=_financials_ok,
        news_fn=_news_ok,
    )
    assert out.quote is not None
    assert out.financials is not None
    assert len(out.news) == 10
    assert not out.degraded
    assert out.billable_units == 1


async def test_scrape_quote_only() -> None:
    inp = CafeFScrapeInput(
        symbol="VCB",
        include_financials=False,
        include_news=False,
    )
    out = await scrape_cafef(inp, quote_fn=_quote_ok)
    assert out.quote is not None
    assert out.financials is None
    assert out.news == []
    assert not out.degraded


async def test_scrape_degrades_on_rate_limit() -> None:
    async def _rate_limited(symbol: str) -> dict:
        raise CafeFRateLimitedError("429")

    inp = CafeFScrapeInput(symbol="VCB")
    out = await scrape_cafef(inp, quote_fn=_rate_limited)
    assert out.degraded
    assert out.degradation_reason == "rate_limited"
    assert out.billable_units == 0


async def test_scrape_degrades_on_decode_error() -> None:
    async def _bad(symbol: str) -> dict:
        raise CafeFDecodeError("bad json")

    inp = CafeFScrapeInput(symbol="VCB")
    out = await scrape_cafef(inp, quote_fn=_bad)
    assert out.degraded
    assert out.degradation_reason == "decode_error"


async def test_scrape_skips_financials_on_degraded_quote() -> None:
    calls = []

    async def _quote_ok(symbol: str) -> dict:
        return _demo_quote_raw(symbol)

    async def _financials_bad(symbol: str) -> dict:
        calls.append("financials")
        raise CafeFDecodeError("fail")

    inp = CafeFScrapeInput(symbol="VCB", include_financials=True)
    out = await scrape_cafef(
        inp,
        quote_fn=_quote_ok,
        financials_fn=_financials_bad,
    )
    assert out.degraded
    assert out.degradation_reason == "decode_error"
    assert out.quote is not None  # partial data preserved
