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


async def _fake_search_fetch(
    query: str, search_type: str, page: int
) -> tuple[str, int]:
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
    inp = MasothueSearchInput(query="vinamilk", tax_code="0314539065", max_items=2)
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
    monkeypatch.setattr("app.config.config.MASOTHUE_PAGE_DELAY_S", 0, raising=False)


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

    async def paged_search_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
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

    async def exact_match_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
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

    async def tracking_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
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

    async def tracking_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
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

    async def rate_limited_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
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
async def test_scrape_pagination_respects_max_pages() -> None:
    """The scraper must fetch exactly max_pages pages and no more (kills Add_LShift on range)."""
    pages_fetched: list[int] = []

    async def paged_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        pages_fetched.append(page)
        html = f"""
        <div class="search-results">
            <h3><a href="/p{page}">Company {page}</a></h3>
            <p>Mã số thuế: 031453906{page}</p>
        </div>
        <div class="pagination">
            <span class="page-numbers current">{page}</span>
            <a class="page-numbers" href="?page={page + 1}">{page + 1}</a>
        </div>
        """
        return html, 200

    inp = MasothueSearchInput(
        query="vinamilk", max_items=10, max_pages=2, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=paged_fetch)

    assert out.degraded is False
    assert pages_fetched == [1, 2]
    assert out.total_items == 2


@pytest.mark.asyncio
async def test_scrape_retry_upper_bound_uses_max_retries_plus_one(
    monkeypatch: Any,
) -> None:
    """range(_MAX_RETRIES + 1) must be used; range(_MAX_RETRIES << 1) would over-run."""
    calls: list[int] = []

    async def rate_limited_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
        calls.append(page)
        raise MasothueRateLimitedError("429")

    from app.proprietary.platforms.masothue import scraper as scraper_module

    monkeypatch.setattr(scraper_module, "_MAX_RETRIES", 0)

    inp = MasothueSearchInput(query="vinamilk", max_items=10, resolve_detail=False)
    out = await scrape_masothue(inp, search_fetch_fn=rate_limited_fetch)

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_scraper_zero_bounds() -> None:
    calls: list[int] = []

    async def tracking_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
        calls.append(page)
        return SEARCH_HTML, 200

    inp1 = MasothueSearchInput(query="vinamilk", max_items=0, max_pages=5)
    out1 = await scrape_masothue(inp1, search_fetch_fn=tracking_fetch)
    assert out1.items == []
    assert out1.total_items == 0
    assert out1.degraded is False
    assert len(calls) == 0

    inp2 = MasothueSearchInput(query="vinamilk", max_items=10, max_pages=0)
    out2 = await scrape_masothue(inp2, search_fetch_fn=tracking_fetch)
    assert out2.items == []
    assert out2.total_items == 0
    assert out2.degraded is False
    assert len(calls) == 0

    inp3 = MasothueSearchInput(
        query="vinamilk", max_items=1, max_pages=1, resolve_detail=False
    )
    out3 = await scrape_masothue(inp3, search_fetch_fn=tracking_fetch)
    assert len(calls) == 1
    assert out3.total_items == 1


@pytest.mark.asyncio
async def test_scraper_search_generic_exc_retries_and_recovers() -> None:
    calls = 0

    async def retry_search_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise RuntimeError(f"attempt {calls} failed")
        return SEARCH_HTML, 200

    inp = MasothueSearchInput(
        query="vinamilk", max_pages=1, max_items=2, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=retry_search_fetch)
    assert out.degraded is False
    assert out.total_items == 2
    assert calls == 3


@pytest.mark.asyncio
async def test_scraper_rate_limit_retries_and_recovers() -> None:
    calls = 0

    async def retry_429_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise MasothueRateLimitedError(f"attempt {calls} 429")
        return SEARCH_HTML, 200

    inp = MasothueSearchInput(
        query="vinamilk", max_pages=1, max_items=2, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=retry_429_fetch)
    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert out.total_items == 2
    assert calls == 3


@pytest.mark.asyncio
async def test_scraper_page_pacing_sleep_called_between_pages(monkeypatch: Any) -> None:
    """Sleep is called strictly between page 1 and page 2 (before page 2 fetch, never after page 2)."""
    import asyncio

    events: list[str] = []

    async def fake_sleep(duration: float) -> None:
        events.append("sleep")

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def paged_fetch(
        query: str, search_type: str, page: int, **kwargs: Any
    ) -> tuple[str, int]:
        events.append(f"fetch_{page}")
        html = f"""
        <div class="search-results">
            <h3><a href="/p{page}">Company {page}</a></h3>
            <p>Mã số thuế: 031453906{page}</p>
        </div>
        <div class="pagination">
            <span class="page-numbers current">{page}</span>
            <a class="page-numbers" href="?page={page + 1}">{page + 1}</a>
        </div>
        """
        return html, 200

    inp = MasothueSearchInput(
        query="vinamilk", max_items=10, max_pages=2, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=paged_fetch)

    assert out.degraded is False
    assert out.total_items == 2
    # Order must be fetch_1 -> sleep -> fetch_2 (kills if page == max_pages mutant)
    assert events == ["fetch_1", "sleep", "fetch_2"]


@pytest.mark.asyncio
async def test_scraper_helpers() -> None:
    import re

    from app.proprietary.platforms.masothue.scraper import (
        _matches_filter,
        _normalize_tax_code,
        _now_iso,
        _page_delay,
        _timeout,
    )

    ts = _now_iso()
    assert ts.endswith("Z")
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", ts)
    assert len(ts) == 24

    assert _normalize_tax_code(None) is None
    assert _normalize_tax_code("") is None
    assert _normalize_tax_code("   -   ") is None
    assert _normalize_tax_code(" 031-453 9064 ") == "0314539064"

    company = MasothueCompany(name="Vinamilk", tax_code="031-453 9064")
    assert _matches_filter(company, None) is True
    assert _matches_filter(company, "") is True
    assert _matches_filter(company, "0314539064") is True
    assert _matches_filter(company, "031-453-9064") is True
    assert _matches_filter(company, "9999999999") is False

    # Tax code greater than and less than filter (kills >= and <= mutants)
    assert (
        _matches_filter(MasothueCompany(tax_code="0314539065"), "0314539064") is False
    )
    assert (
        _matches_filter(MasothueCompany(tax_code="0314539063"), "0314539064") is False
    )

    assert _page_delay() >= 0.0
    assert _timeout() >= 0.0


@pytest.mark.asyncio
async def test_scrape_detail_rate_limited_degrades() -> None:
    async def rate_limited_detail(url: str) -> str:
        raise MasothueRateLimitedError("429 detail")

    inp = MasothueSearchInput(query="vinamilk", max_pages=1, max_items=2)
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=rate_limited_detail,
    )
    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"


@pytest.mark.asyncio
async def test_scrape_cap_stops_at_exact_count() -> None:
    inp = MasothueSearchInput(
        query="vinamilk", max_pages=1, max_items=1, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=_fake_search_fetch)
    assert out.total_items == 1
    assert len(out.items) == 1
    assert out.items[0].tax_code == "0314539064"


@pytest.mark.asyncio
async def test_scrape_search_decode_error_degrades() -> None:
    from app.proprietary.platforms.masothue.fetch import MasothueDecodeError

    async def decode_err_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
        raise MasothueDecodeError("bad html")

    inp = MasothueSearchInput(query="vinamilk", max_items=10)
    out = await scrape_masothue(inp, search_fetch_fn=decode_err_fetch)
    assert out.degraded is True
    assert out.degradation_reason == "decode_error"
    assert out.total_items == 0


@pytest.mark.asyncio
async def test_scrape_search_access_blocked_and_timeout_degrade() -> None:
    from app.proprietary.platforms.masothue.fetch import (
        MasothueAccessBlockedError,
        MasothueTimeoutError,
    )

    async def blocked_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        raise MasothueAccessBlockedError("403")

    inp = MasothueSearchInput(query="vinamilk", max_items=10)
    out = await scrape_masothue(inp, search_fetch_fn=blocked_fetch)
    assert out.degraded is True
    assert out.degradation_reason == "access_blocked"

    async def timeout_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        raise MasothueTimeoutError("timeout")

    out_to = await scrape_masothue(inp, search_fetch_fn=timeout_fetch)
    assert out_to.degraded is True
    assert out_to.degradation_reason == "timeout"

    async def generic_err_fetch(
        query: str, search_type: str, page: int
    ) -> tuple[str, int]:
        raise RuntimeError("generic network fail")

    out_gen = await scrape_masothue(inp, search_fetch_fn=generic_err_fetch)
    assert out_gen.degraded is True
    assert out_gen.degradation_reason == "api_error"


@pytest.mark.asyncio
async def test_scrape_deduplicates_companies_without_tax_code() -> None:
    html = """
    <div>
        <div><h3><a href="/url-a">Company Alpha</a></h3></div>
        <div><h3><a href="/url-b">Company Beta</a></h3></div>
        <div><h3><a href="/url-a">Company Alpha</a></h3></div>
    </div>
    """

    async def fake_search(query: str, search_type: str, page: int) -> tuple[str, int]:
        return html, 200

    inp = MasothueSearchInput(
        query="test", max_pages=1, max_items=10, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=fake_search)
    assert out.degraded is False
    assert out.degradation_reason is None
    assert out.total_items == 2
    names = [c.name for c in out.items]
    assert "Company Alpha" in names
    assert "Company Beta" in names


@pytest.mark.asyncio
async def test_scrape_detail_decode_error_keeps_summary() -> None:
    from app.proprietary.platforms.masothue.fetch import MasothueDecodeError

    async def decode_err_detail(url: str) -> str:
        raise MasothueDecodeError("malformed detail")

    inp = MasothueSearchInput(query="vinamilk", max_pages=1, max_items=2)
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=decode_err_detail,
    )

    assert out.degraded is False
    assert out.total_items == 2
    assert out.items[0].tax_code == "0314539064"


@pytest.mark.asyncio
async def test_scrape_detail_blocked_or_generic_exc_skips_item_and_continues() -> None:
    """When detail fetch fails for first item, first item is skipped and second item is fetched."""
    from app.proprietary.platforms.masothue.fetch import MasothueAccessBlockedError

    calls = 0

    async def partial_fail_detail(url: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise MasothueAccessBlockedError("blocked")
        return DETAIL_HTML.replace("0314539064", "0314539065")

    inp = MasothueSearchInput(query="vinamilk", max_pages=1, max_items=2)
    out = await scrape_masothue(
        inp,
        search_fetch_fn=_fake_search_fetch,
        detail_fetch_fn=partial_fail_detail,
    )

    assert out.degraded is False
    assert out.total_items == 1
    assert out.items[0].tax_code == "0314539065"
    assert out.items[0].address is not None


@pytest.mark.asyncio
async def test_scrape_second_page_empty_stops_without_degrading() -> None:
    """If page 1 has items and page 2 has no items, the run is complete and not degraded."""

    async def search_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        if page == 1:
            return SEARCH_HTML, 200
        return "<html><body><div></div></body></html>", 200

    inp = MasothueSearchInput(
        query="vinamilk", max_pages=3, max_items=10, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=search_fetch)

    assert out.degraded is False
    assert out.total_items == 2


@pytest.mark.asyncio
async def test_scrape_deduplicates_by_tax_code_and_name_url() -> None:
    """Deduplication keys by tax_code and fallback name|detail_url."""
    dup_html = """
    <div class="search-results">
        <h3><a href="/0314539064-a">Vinamilk</a></h3>
        <p>Mã số thuế: 0314539064</p>
    </div>
    <div class="search-results">
        <h3><a href="/0314539064-b">Vinamilk Dup</a></h3>
        <p>Mã số thuế: 0314539064</p>
    </div>
    <div class="search-results">
        <h3><a href="/no-tax-c">No Tax Unique</a></h3>
    </div>
    <div class="search-results">
        <h3><a href="/no-tax-c">No Tax Unique</a></h3>
    </div>
    """

    async def dup_fetch(query: str, search_type: str, page: int) -> tuple[str, int]:
        return dup_html, 200

    inp = MasothueSearchInput(
        query="vinamilk", max_pages=1, max_items=10, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=dup_fetch)
    assert out.total_items == 2
    assert out.items[0].tax_code == "0314539064"
    assert out.items[1].name == "No Tax Unique"


def test_scraper_timeout_helper(monkeypatch: Any) -> None:
    import app.proprietary.platforms.masothue.scraper as scraper_mod
    from app.proprietary.platforms.masothue.scraper import _timeout

    monkeypatch.setattr(scraper_mod, "config", object())
    assert _timeout() == 30.0

    monkeypatch.setattr(
        scraper_mod, "config", type("C", (), {"MASOTHUE_TIMEOUT_S": 15.5})()
    )
    assert _timeout() == 15.5

    monkeypatch.setattr(
        scraper_mod, "config", type("C", (), {"MASOTHUE_TIMEOUT_S": -5.0})()
    )
    assert _timeout() == 0.0


@pytest.mark.asyncio
async def test_scraper_zero_bounds_return_empty() -> None:
    search_called = False

    async def tracking_search(*args: Any, **kwargs: Any) -> tuple[str, int]:
        nonlocal search_called
        search_called = True
        return SEARCH_HTML, 200

    res1 = await scrape_masothue(
        MasothueSearchInput(query="vnm", max_items=0, max_pages=1),
        search_fetch_fn=tracking_search,
    )
    assert search_called is False
    assert res1.total_items == 0
    assert res1.items == []

    res2 = await scrape_masothue(
        MasothueSearchInput(query="vnm", max_items=5, max_pages=0),
        search_fetch_fn=tracking_search,
    )
    assert search_called is False
    assert res2.total_items == 0
    assert res2.items == []


@pytest.mark.asyncio
async def test_scraper_exact_retry_attempts_count(monkeypatch: Any) -> None:
    """_MAX_RETRIES=2 means exactly 3 attempts before degrading."""
    import asyncio

    async def fake_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    call_count = 0

    async def always_rate_limited(
        query: str, search_type: str, page: int, **kwargs: Any
    ) -> tuple[str, int]:
        nonlocal call_count
        call_count += 1
        raise MasothueRateLimitedError("rate limited")

    inp = MasothueSearchInput(query="vinamilk", max_pages=1, max_items=5)
    out = await scrape_masothue(inp, search_fetch_fn=always_rate_limited)

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert call_count == 3  # _MAX_RETRIES (2) + 1


@pytest.mark.asyncio
async def test_scraper_retry_on_first_attempt_succeeds_on_second(
    monkeypatch: Any,
) -> None:
    import asyncio

    sleep_called = 0

    async def fake_sleep(_: float) -> None:
        nonlocal sleep_called
        sleep_called += 1

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    attempts = 0

    async def retry_search(
        query: str, search_type: str, page: int, **kwargs: Any
    ) -> tuple[str, int]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise MasothueRateLimitedError("first attempt rate limited")
        return SEARCH_HTML, 200

    inp = MasothueSearchInput(
        query="vinamilk", max_pages=1, max_items=5, resolve_detail=False
    )
    out = await scrape_masothue(inp, search_fetch_fn=retry_search)

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert out.total_items == 2
    assert attempts == 2
    assert sleep_called == 1
