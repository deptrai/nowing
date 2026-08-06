"""Unit tests for the masothue.com scraper orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.proprietary.platforms.masothue.schemas import MasothueSearchInput
from app.proprietary.platforms.masothue.scraper import scrape_masothue

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_HTML = (FIXTURES / "search_page.html").read_text()
DETAIL_HTML = (FIXTURES / "detail_page.html").read_text()


async def _fake_search_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
    return SEARCH_HTML, 200


async def _fake_detail_fetch(url: str) -> str:
    tax_code = url.rsplit("/", 1)[-1].split("-", 1)[0] if "/" in url else "0000000000"
    return DETAIL_HTML.replace(">0314539064<", f">{tax_code}<")


@pytest.mark.asyncio
async def test_scrape_returns_companies_with_detail() -> None:
    inp = MasothueSearchInput(query="vinamilk", max_pages=1, max_items=2)
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=_fake_detail_fetch,
    )
    assert out.degraded is False
    assert out.total_items == 2
    assert out.items[0].name == "Công ty TNHH Vinamilk Tân Sơn"
    assert out.items[0].main_industry == "Sản xuất sữa"


@pytest.mark.asyncio
async def test_scrape_respects_max_items() -> None:
    inp = MasothueSearchInput(query="vinamilk", max_pages=5, max_items=1)
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=_fake_detail_fetch,
    )
    assert out.total_items == 1
    assert len(out.items) == 1


@pytest.mark.asyncio
async def test_scrape_zero_max_items() -> None:
    inp = MasothueSearchInput(query="vinamilk", max_items=0)
    out = await scrape_masothue(inp)
    assert out.total_items == 0
    assert out.degraded is False


@pytest.mark.asyncio
async def test_scrape_filters_by_tax_code() -> None:
    inp = MasothueSearchInput(
        query="vinamilk", tax_code="0314539065", max_items=2
    )
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=_fake_detail_fetch,
    )
    assert out.total_items == 1
    assert out.items[0].tax_code == "0314539065"


@pytest.mark.asyncio
async def test_scrape_empty_first_page_degrades() -> None:
    async def empty_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        return "<html><body></body></html>", 200

    inp = MasothueSearchInput(query="xyz", max_items=10)
    out = await scrape_masothue(inp, search_fetch_fn=empty_fetch)
    assert out.degraded is True
    assert out.degradation_reason == "empty"
    assert out.total_items == 0
