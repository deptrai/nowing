"""Offline orchestrator tests for the Batdongsan scraper.

The network boundary (``fetch_listings``) is injected as a fake. Tests cover
pagination, caps, and degradation.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.proprietary.platforms.batdongsan.fetch import (
    BatdongsanAccessBlockedError,
    BatdongsanRateLimitedError,
)
from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput
from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan

pytestmark = pytest.mark.unit


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
