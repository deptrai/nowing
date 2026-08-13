"""Integration tests for the CafeF capability end-to-end."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.cafef.scrape.executor import build_scrape_executor
from app.capabilities.cafef.scrape.schemas import ScrapeInput
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.db import Document, DocumentType, Workspace
from app.proprietary.platforms.cafef import fetch


def _quote_response() -> dict:
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


def _financial_response() -> dict:
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


def _news_response() -> str:
    return """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>VCB công bố BCTC</title>
    <link>https://cafef.vn/vcb.chn</link>
    <pubDate>Fri, 01 Jan 26 00:00:00 +0700</pubDate>
    <description>Tóm tắt</description>
  </item>
</channel></rss>
    """


@pytest.fixture(autouse=True)
def _force_live_mode(monkeypatch):
    monkeypatch.setattr(config, "CAFEF_DEMO_MODE", False)
    monkeypatch.setattr(config, "CAFEF_TIMEOUT_S", 5.0)
    monkeypatch.setattr(config, "CAFEF_QUOTE_URL", "https://apiweb.cafef.vn/api/v1/Stock/Quote?symbol={symbol}")
    monkeypatch.setattr(config, "CAFEF_NEWS_URL", "https://apiweb.cafef.vn/api/v1/News/Search?symbol={symbol}&pageSize={max_news}")
    monkeypatch.setattr(fetch, "_last_request_at", None)


async def test_cafef_scrape_indexes_news(
    db_workspace: Workspace,
    db_session: AsyncSession,
    http_mock,
    patched_embed_texts,
    patched_chunk_text,
) -> None:
    http_mock(
        {
            (
                "https://apiweb.cafef.vn/api/v1/Stock/Quote",
                (("symbol", "VCB"),),
            ): (200, _quote_response()),
            (
                "https://apiweb.cafef.vn/api/v2/BCTC/GetReportCDKT",
                (("symbol", "VCB"),),
            ): (200, _financial_response()),
            (
                "https://apiweb.cafef.vn/api/v1/BCTC/GetReportDetail",
                (("symbol", "VCB"),),
            ): (200, _financial_response()),
            (
                "https://apiweb.cafef.vn/api/v1/BCTC/GetReportLCTT",
                (("symbol", "VCB"),),
            ): (200, _financial_response()),
            (
                "https://apiweb.cafef.vn/api/v1/News/Search",
                (("symbol", "VCB"), ("pageSize", 5)),
            ): (200, _news_response()),
        }
    )

    executor = build_scrape_executor()
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    out = await executor(
        ScrapeInput(
            symbol="VCB",
            include_financials=True,
            include_news=True,
            max_news=5,
        ),
        ctx=ctx,
    )

    assert not out.degraded
    assert out.quote is not None
    assert out.quote.current_price == 80.5
    assert out.financials is not None
    assert len(out.news) == 1
    assert out.total_items == 1

    # News indexing creates a NEWS_CONNECTOR document.
    result = await db_session.execute(
        select(Document)
        .where(Document.workspace_id == db_workspace.id)
        .where(Document.document_type == DocumentType.NEWS_CONNECTOR)
    )
    docs = result.scalars().all()
    assert len(docs) == 1
    assert docs[0].title == "VCB công bố BCTC"


async def test_cafef_scrape_degraded_on_429(
    db_workspace: Workspace,
    http_mock,
) -> None:
    http_mock(
        {
            (
                "https://apiweb.cafef.vn/api/v1/Stock/Quote",
                (("symbol", "VCB"),),
            ): (429, {"error": "rate limited"}),
        }
    )

    executor = build_scrape_executor()
    ctx = CapabilityContext(session=None, workspace_id=db_workspace.id)  # type: ignore[arg-type]
    out = await executor(
        ScrapeInput(symbol="VCB"),
        ctx=ctx,
    )

    assert out.degraded
    assert out.degradation_reason == "rate_limited"
    assert out.total_items == 0
