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
    monkeypatch.setattr(config, "CAFEF_QUOTE_URL", "https://apiweb.cafef.vn/api/v1/Stock/Quote?symbol={symbol}")
    monkeypatch.setattr(config, "CAFEF_NEWS_URL", "https://apiweb.cafef.vn/api/v1/News/Search?symbol={symbol}&pageSize={max_news}")
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
    rss = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>VCB công bố BCTC</title>
    <link>https://cafef.vn/vcb.chn</link>
    <pubDate>Fri, 14 Aug 26 00:00:00 +0700</pubDate>
    <description>VCB tăng trưởng.</description>
  </item>
</channel></rss>
    """
    http_mock(
        {
            (
                "https://apiweb.cafef.vn/api/v1/News/Search",
                (("symbol", "VCB"), ("pageSize", 5)),
            ): (200, rss),
        }
    )
    items = await fetch_news("VCB", max_news=5)
    assert len(items) == 1
    assert items[0]["title"] == "VCB công bố BCTC"


def test_parse_rss_news() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title><![CDATA[VCB công bố BCTC]]></title>
      <link>https://cafef.vn/vcb.chn</link>
      <pubDate>Fri, 14 Aug 26 00:00:00 +0700</pubDate>
      <description><![CDATA[<a href="https://cafef.vn/vcb.chn">VCB</a> tăng trưởng.]]></description>
    </item>
    <item>
      <title><![CDATA[Tin chung]]></title>
      <link>https://cafef.vn/general.chn</link>
      <pubDate>Fri, 14 Aug 26 00:00:00 +0700</pubDate>
      <description><![CDATA[Thị trường chứng khoán]]></description>
    </item>
  </channel>
</rss>
    """
    items = fetch._parse_rss_news(xml, "VCB", 5)
    assert len(items) == 1
    assert items[0]["title"] == "VCB công bố BCTC"
    assert items[0]["url"] == "https://cafef.vn/vcb.chn"
    assert "VCB" in items[0]["summary"]


def test_parse_rss_news_no_symbol_filter() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Tin 1</title>
      <link>https://cafef.vn/1.chn</link>
    </item>
    <item>
      <title>Tin 2</title>
      <link>https://cafef.vn/2.chn</link>
    </item>
  </channel>
</rss>
    """
    items = fetch._parse_rss_news(xml, None, 1)
    assert len(items) == 1
    assert items[0]["title"] == "Tin 1"


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
