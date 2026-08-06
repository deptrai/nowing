"""Unit tests for the masothue.com scraper orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.proprietary.platforms.masothue.fetch import MasothueRateLimitedError
from app.proprietary.platforms.masothue.schemas import (
    MasothueCompany,
    MasothueSearchInput,
)
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



@pytest.fixture(autouse=True)
def _no_page_delay(monkeypatch):
    """Disable inter-request pacing so unit tests run quickly."""
    monkeypatch.setattr(
        "app.config.config.MASOTHUE_PAGE_DELAY_S", 0, raising=False
    )


@pytest.mark.asyncio
async def test_scrape_resolve_detail_false_skips_detail_fetch() -> None:
    """When resolve_detail=False the scraper returns summary cards only."""
    calls: list[str] = []

    async def tracking_detail_fetch(url: str) -> str:
        calls.append(url)
        return DETAIL_HTML

    inp = MasothueSearchInput(
        query="vinamilk", max_pages=1, max_items=2, resolve_detail=False
    )
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=tracking_detail_fetch,
    )

    assert out.degraded is False
    assert out.total_items == 2
    assert not calls
    assert out.items[0].tax_code == "0314539064"


@pytest.mark.asyncio
async def test_scrape_include_phone_returns_phone() -> None:
    """When include_phone=True, the detail parser exposes the phone field."""
    inp = MasothueSearchInput(
        query="vinamilk", max_pages=1, max_items=1, include_phone=True
    )
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=_fake_detail_fetch,
    )

    assert out.total_items == 1
    assert out.items[0].phone == "028 1234 5678"


@pytest.mark.asyncio
async def test_scrape_stops_when_no_next_page() -> None:
    """parse_pagination is used and the scraper stops when there is no next page."""
    pages_fetched: list[int] = []

    async def paged_search_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        pages_fetched.append(page)
        return SEARCH_HTML, 200

    inp = MasothueSearchInput(query="vinamilk", max_pages=5, max_items=1)
    out = await scrape_masothue(
        inp,
        search_fetch_fn=paged_search_fetch,
        detail_fetch_fn=_fake_detail_fetch,
    )

    assert out.total_items == 1
    # The fixture has page 1 and a link to page 2, but cap is reached on page 1
    # before page 2 is fetched.
    assert pages_fetched == [1]


@pytest.mark.asyncio
async def test_scrape_detail_rate_limit_degrades() -> None:
    """A 429 on a detail fetch degrades the run and returns partial results."""
    from app.proprietary.platforms.masothue.fetch import MasothueRateLimitedError

    async def rate_limited_detail_fetch(url: str) -> str:
        raise MasothueRateLimitedError("429")

    inp = MasothueSearchInput(query="vinamilk", max_pages=1, max_items=2)
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=rate_limited_detail_fetch,
    )

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert out.total_items == 0


@pytest.mark.asyncio
async def test_scrape_exact_match_with_tax_code_filter() -> None:
    """A 302 redirect exact-match plus a tax_code filter returns the one match."""
    async def exact_match_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        return (
            "<div class='search-results'><h3><a href='/0314539064-cong-ty'>Query</a></h3>"
            "<p>Mã số thuế: 0314539064</p></div>",
            200,
        )

    async def detail_fetch(url: str) -> str:
        return DETAIL_HTML

    inp = MasothueSearchInput(
        query="0314539064", tax_code="0314539064", max_pages=1, max_items=1
    )
    out = await scrape_masothue(
        inp,
        search_fetch_fn=exact_match_fetch,
        detail_fetch_fn=detail_fetch,
    )

    assert out.degraded is False
    assert out.total_items == 1
    assert out.items[0].tax_code == "0314539064"


@pytest.mark.asyncio
async def test_scrape_zero_max_items_does_not_fetch() -> None:
    """Boundary: max_items=0 must short-circuit and never call the search fetcher."""
    calls: list[int] = []

    async def tracking_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        calls.append(page)
        return SEARCH_HTML, 200

    inp = MasothueSearchInput(query="vinamilk", max_items=0)
    out = await scrape_masothue(inp, search_fetch_fn=tracking_fetch)

    assert out.total_items == 0
    assert out.degraded is False
    assert calls == []


@pytest.mark.asyncio
async def test_scrape_zero_max_pages_does_not_fetch() -> None:
    """Boundary: max_pages=0 must short-circuit and never call the search fetcher."""
    calls: list[int] = []

    async def tracking_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        calls.append(page)
        return SEARCH_HTML, 200

    inp = MasothueSearchInput(query="vinamilk", max_pages=0)
    out = await scrape_masothue(inp, search_fetch_fn=tracking_fetch)

    assert out.total_items == 0
    assert out.degraded is False
    assert calls == []


@pytest.mark.asyncio
async def test_scrape_retries_then_degrades_on_rate_limit() -> None:
    """The scraper retries _MAX_RETRIES times before degrading on rate limit."""
    calls: list[int] = []

    async def rate_limited_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        calls.append(page)
        raise MasothueRateLimitedError("429")

    from app.proprietary.platforms.masothue.fetch import MasothueRateLimitedError

    inp = MasothueSearchInput(query="vinamilk", max_items=10)
    out = await scrape_masothue(inp, search_fetch_fn=rate_limited_fetch)

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert len(calls) == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_degrade_reason_from_exc_maps_exception_types() -> None:
    """AddNot / exception type mapping must return the right degradation reason."""
    from app.proprietary.platforms.masothue.fetch import (
        MasothueAccessBlockedError,
        MasothueDecodeError,
        MasothueRateLimitedError,
        MasothueTimeoutError,
    )
    from app.proprietary.platforms.masothue.scraper import _degrade_reason_from_exc

    assert _degrade_reason_from_exc(MasothueRateLimitedError("x")) == "rate_limited"
    assert _degrade_reason_from_exc(MasothueTimeoutError("x")) == "timeout"
    assert _degrade_reason_from_exc(MasothueDecodeError("x")) == "decode_error"
    assert _degrade_reason_from_exc(MasothueAccessBlockedError("x")) == "access_blocked"
    assert _degrade_reason_from_exc(RuntimeError("x")) == "api_error"


@pytest.mark.asyncio
async def test_scrape_pagination_respects_max_pages(monkeypatch: Any) -> None:
    """The scraper must fetch exactly max_pages pages and no more (kills Add_LShift on range)."""
    pages_fetched: list[int] = []

    async def fake_search_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        pages_fetched.append(page)
        return (f"<html><body>page {page}</body></html>", 200)

    from app.proprietary.platforms.masothue import scraper as scraper_module

    def fake_parse_search_results(html: str) -> list[MasothueCompany]:
        return [
            MasothueCompany(
                name=f"Company page {html}",
                tax_code=None,
                detail_url=None,
            )
        ]

    def fake_parse_pagination(html: str) -> tuple[int, int | None]:
        # Always claim a next page so the loop relies on max_pages to stop.
        current = int(html.split("page ")[1].split("<")[0])
        return current, current + 1

    monkeypatch.setattr(scraper_module, "parse_search_results", fake_parse_search_results)
    monkeypatch.setattr(scraper_module, "parse_pagination", fake_parse_pagination)

    inp = MasothueSearchInput(query="vinamilk", max_items=10, max_pages=2, resolve_detail=False)
    out = await scrape_masothue(inp, search_fetch_fn=fake_search_fetch)

    assert out.degraded is False
    assert pages_fetched == [1, 2]


@pytest.mark.asyncio
async def test_scrape_retry_upper_bound_uses_max_retries_plus_one(monkeypatch: Any) -> None:
    """range(_MAX_RETRIES + 1) must be used; range(_MAX_RETRIES << 1) would over-run."""
    calls: list[int] = []

    async def rate_limited_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        calls.append(page)
        raise MasothueRateLimitedError("429")

    from app.proprietary.platforms.masothue import scraper as scraper_module

    monkeypatch.setattr(scraper_module, "_MAX_RETRIES", 0)

    inp = MasothueSearchInput(query="vinamilk", max_items=10, resolve_detail=False)
    out = await scrape_masothue(inp, search_fetch_fn=rate_limited_fetch)

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert len(calls) == 1