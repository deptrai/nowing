"""Fetch-layer tests using a fake httpx client."""

from __future__ import annotations

import time

import pytest

from app.config import config
from app.proprietary.platforms.cafef import fetch
from app.proprietary.platforms.cafef.fetch import (
    fetch_financials,
    fetch_news,
    fetch_quote,
)


def _mock_quote_response() -> dict:
    return {
        "symbol": "VCB",
        "price": 80.5,
        "open": 79.0,
        "high": 81.0,
        "low": 78.5,
        "close": 80.0,
        "volume": 1_000_000,
        "change": 0.5,
        "changePercent": 0.63,
        "keyRatios": {"pe": 12.3, "pb": 1.5},
    }


def _mock_financial_response() -> dict:
    return {
        "isSuccess": True,
        "value": {
            "templace": [{"code": "10", "name": "Doanh thu thuần"}],
            "data": [
                {
                    "symbol": "VCB",
                    "time": "Q1-2026",
                    "data": [{"code": "10", "value": 1000}],
                }
            ],
        },
    }


def _mock_news_response() -> list[dict]:
    return [
        {
            "title": "VCB công bố BCTC",
            "url": "https://cafef.vn/vcb.chn",
            "publishedAt": "2026-01-01",
            "summary": "Tóm tắt",
        }
    ]


@pytest.fixture(autouse=True)
def _reset_demo_mode(monkeypatch):
    """Force demo mode off so mocked HTTP routes are exercised."""
    monkeypatch.setattr(config, "CAFEF_DEMO_MODE", False)
    monkeypatch.setattr(config, "CAFEF_TIMEOUT_S", 5.0)
    monkeypatch.setattr(fetch, "_last_request_at", None)


async def test_fetch_quote(http_mock) -> None:
    http_mock(
        {
            ("https://apiweb.cafef.vn/api/v1/Stock/Quote", (("symbol", "VCB"),)): (
                200,
                _mock_quote_response(),
            ),
        }
    )
    raw = await fetch_quote("VCB")
    assert raw["symbol"] == "VCB"


async def test_fetch_financials(http_mock) -> None:
    http_mock(
        {
            (
                "https://apiweb.cafef.vn/api/v2/BCTC/GetReportCDKT",
                (("symbol", "VCB"),),
            ): (200, _mock_financial_response()),
            (
                "https://apiweb.cafef.vn/api/v1/BCTC/GetReportDetail",
                (("symbol", "VCB"),),
            ): (200, _mock_financial_response()),
            (
                "https://apiweb.cafef.vn/api/v1/BCTC/GetReportLCTT",
                (("symbol", "VCB"),),
            ): (200, _mock_financial_response()),
        }
    )
    raw = await fetch_financials("VCB")
    assert "balance_sheet" in raw
    assert raw["income_statement"]["isSuccess"] is True


async def test_fetch_news(http_mock) -> None:
    http_mock(
        {
            (
                "https://apiweb.cafef.vn/api/v1/News/Search",
                (("symbol", "VCB"), ("pageSize", 5)),
            ): (200, _mock_news_response()),
        }
    )
    items = await fetch_news("VCB", max_news=5)
    assert len(items) == 1
    assert items[0]["title"] == "VCB công bố BCTC"


async def test_rate_limit_throttles(monkeypatch, http_mock) -> None:
    """Two consecutive calls must be spaced by at least the configured interval."""
    monkeypatch.setattr(config, "CAFEF_RATE_LIMIT_RPS", 4.0)
    # interval = 0.25 s
    monkeypatch.setattr(fetch, "_last_request_at", None)

    http_mock(
        {
            ("https://apiweb.cafef.vn/api/v1/Stock/Quote", (("symbol", "VCB"),)): (
                200,
                _mock_quote_response(),
            ),
        }
    )

    t0 = time.perf_counter()
    await fetch_quote("VCB")
    await fetch_quote("VCB")
    elapsed = time.perf_counter() - t0

    assert elapsed >= 0.20
