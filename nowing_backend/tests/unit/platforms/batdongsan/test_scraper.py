"""Offline orchestrator tests for the Batdongsan scraper.

The network boundary (``fetch_listings``) is injected as a fake. Tests cover
pagination, caps, and degradation.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.proprietary.platforms.batdongsan.fetch import (
    BatdongsanAccessBlockedError,
    BatdongsanDecodeError,
    BatdongsanRateLimitedError,
)
from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput
from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan

pytestmark = pytest.mark.unit

_MODULE = "app.proprietary.platforms.batdongsan.scraper"


@pytest.fixture(autouse=True)
def _no_page_delay(mocker):
    """Keep pacing sleeps out of offline tests."""
    mocker.patch(f"{_MODULE}.asyncio.sleep")


def _listing(id_: int, title: str = "Listing") -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "address": "Hà Nội",
        "price": "1 Tỷ",
        "area": "50 m²",
        "date": "01/08/2026",
        "url": f"https://batdongsan.com.vn/p/{id_}.htm",
    }


class _FakeFetcher:
    """Records page payloads and returns canned ``p_sync`` envelopes."""

    def __init__(self, pages: list[list[dict[str, Any]]]):
        self.pages = pages
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        page = payload.get("page", 1)
        if page > len(self.pages):
            return {"data": [], "m": None}
        return {"data": self.pages[page - 1], "m": "ok"}


@pytest.mark.asyncio
async def test_scraper_paginates_until_max_items():
    pages = [[_listing(i) for i in range(1, 6)], [_listing(i) for i in range(6, 11)]]
    fetcher = _FakeFetcher(pages)

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=7,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)

    assert output.total_items == 7
    assert len(output.items) == 7
    assert [item.listing_id for item in output.items] == list(range(1, 8))
    assert output.degraded is False
    assert len(fetcher.calls) == 2


@pytest.mark.asyncio
async def test_scraper_stops_on_empty_page():
    pages = [[_listing(1), _listing(2)], []]
    fetcher = _FakeFetcher(pages)

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=100,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)

    assert output.total_items == 2
    assert len(output.items) == 2
    assert output.degraded is False


@pytest.mark.asyncio
async def test_scraper_empty_first_page_degrades_with_empty_reason():
    pages = [[]]
    fetcher = _FakeFetcher(pages)

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=100,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)

    assert output.total_items == 0
    assert output.degraded is True
    assert output.degradation_reason == "empty"


@pytest.mark.asyncio
async def test_scraper_dedupes_listings_across_pages():
    pages = [
        [_listing(1), _listing(2)],
        [_listing(2), _listing(3)],
        [_listing(4)],
    ]
    fetcher = _FakeFetcher(pages)

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=100,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)

    assert output.total_items == 4
    assert [item.listing_id for item in output.items] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_scraper_decode_error_degrades_with_decode_error():
    async def broken_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
        raise BatdongsanDecodeError("bad wire bytes")

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=10,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=broken_fetcher)

    assert output.degraded is True
    assert output.degradation_reason == "decode_error"
    assert output.total_items == 0


@pytest.mark.asyncio
async def test_scraper_non_list_data_degrades_with_api_error():
    async def weird_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"data": {"unexpected": True}, "m": "ok"}

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=10,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=weird_fetcher)

    assert output.degraded is True
    assert output.degradation_reason == "api_error"
    assert output.total_items == 0


@pytest.mark.asyncio
async def test_scraper_honors_max_pages():
    pages = [
        [_listing(1), _listing(2)],
        [_listing(3), _listing(4)],
        [_listing(5), _listing(6)],
    ]
    fetcher = _FakeFetcher(pages)

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=1,
        max_items=100,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)

    assert output.total_items == 2
    assert len(output.items) == 2
    assert len(fetcher.calls) == 1


@pytest.mark.asyncio
async def test_scraper_returns_degraded_on_api_error():
    async def failing_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
        raise BatdongsanAccessBlockedError("blocked")

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=10,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=failing_fetcher)

    assert output.degraded is True
    assert output.degradation_reason == "api_error"
    assert output.total_items == 0
    assert output.items == []


@pytest.mark.asyncio
async def test_scraper_rate_limited_degrades_after_retry():
    calls = 0

    async def flaky_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise BatdongsanRateLimitedError("429")
        return {"data": [_listing(1)], "m": "ok"}

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="HN",
        max_pages=10,
        max_items=10,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=flaky_fetcher)

    assert output.degraded is True
    assert output.degradation_reason == "rate_limited"


class _FakeWebFetcher:
    """Returns canned web envelopes; records calls."""

    def __init__(self, pages: list[list[dict[str, Any]]]):
        self.pages = pages
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        page = payload.get("page", 1)
        if page > len(self.pages):
            return {"data": [], "m": None}
        data = self.pages[page - 1]
        return {"data": data, "m": "ok" if len(data) >= 20 else None}


@pytest.mark.asyncio
async def test_web_fallback_engages_when_mobile_empty_city_level():
    mobile = _FakeFetcher([[]])
    web = _FakeWebFetcher([[_listing(101), _listing(102)]])

    input_model = BatdongsanScrapeInput(
        listing_type="buy", city="BTH", max_pages=5, max_items=10
    )
    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)

    assert output.total_items == 2
    assert output.degraded is False
    assert [item.listing_id for item in output.items] == [101, 102]
    assert len(mobile.calls) == 1  # only page 1 mobile
    assert len(web.calls) == 1


@pytest.mark.asyncio
async def test_web_fallback_skipped_when_district_filter_present():
    mobile = _FakeFetcher([[]])
    web = _FakeWebFetcher([[_listing(101)]])

    input_model = BatdongsanScrapeInput(
        listing_type="buy", city="BTH", district_id=5, max_pages=5, max_items=10
    )
    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)

    assert output.total_items == 0
    assert output.degraded is True
    assert output.degradation_reason == "empty"
    assert len(web.calls) == 0  # web never called


@pytest.mark.asyncio
async def test_web_fallback_skipped_when_price_bound_present():
    mobile = _FakeFetcher([[]])
    web = _FakeWebFetcher([[_listing(101)]])

    input_model = BatdongsanScrapeInput(
        listing_type="buy",
        city="BTH",
        max_price=5_000_000_000,
        max_pages=5,
        max_items=10,
    )
    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)

    assert output.degraded is True
    assert output.degradation_reason == "empty"
    assert len(web.calls) == 0


@pytest.mark.asyncio
async def test_web_fallback_both_empty_degrades_empty():
    mobile = _FakeFetcher([[]])
    web = _FakeWebFetcher([[]])

    input_model = BatdongsanScrapeInput(
        listing_type="buy", city="BTH", max_pages=5, max_items=10
    )
    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)

    assert output.total_items == 0
    assert output.degraded is True
    assert output.degradation_reason == "empty"


@pytest.mark.asyncio
async def test_web_fallback_paginates_with_web_fetcher():
    mobile = _FakeFetcher([[]])
    web_pages = [
        [_listing(i) for i in range(1, 21)],  # 20 items → m=ok
        [_listing(21), _listing(22)],  # 2 items → m=None
    ]
    web = _FakeWebFetcher(web_pages)

    input_model = BatdongsanScrapeInput(
        listing_type="buy", city="BTH", max_pages=5, max_items=25
    )
    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)

    assert output.total_items == 22
    assert output.degraded is False
    assert len(mobile.calls) == 1  # only page 1
    assert len(web.calls) == 2  # pages 1 + 2


@pytest.mark.asyncio
async def test_web_fallback_not_used_when_mobile_has_data():
    mobile = _FakeFetcher([[_listing(1), _listing(2)]])
    web = _FakeWebFetcher([[_listing(999)]])

    input_model = BatdongsanScrapeInput(
        listing_type="buy", city="HN", max_pages=5, max_items=10
    )
    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)

    assert output.total_items == 2
    assert [item.listing_id for item in output.items] == [1, 2]
    assert len(web.calls) == 0


@pytest.mark.asyncio
async def test_web_fallback_blocked_degrades_empty():
    mobile = _FakeFetcher([[]])

    async def blocked_web(_payload: dict[str, Any]) -> dict[str, Any]:
        raise BatdongsanAccessBlockedError("403")

    input_model = BatdongsanScrapeInput(
        listing_type="buy", city="BTH", max_pages=5, max_items=10
    )
    output = await scrape_batdongsan(
        input_model, fetch_fn=mobile, web_fetch_fn=blocked_web
    )

    assert output.total_items == 0
    assert output.degraded is True
    assert output.degradation_reason == "empty"
