"""Unit tests for the ``batdongsan.scrape`` executor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.capabilities.batdongsan.scrape.executor import build_scrape_executor
from app.capabilities.batdongsan.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.platforms.batdongsan.fetch import (
    BatdongsanAccessBlockedError,
    BatdongsanDecodeError,
    BatdongsanRateLimitedError,
)
from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput

pytestmark = pytest.mark.unit

ScrapeFn = Callable[..., Awaitable[dict[str, Any]]]


class _FakeScraper:
    """Records the actor input it was called with; returns canned output."""

    def __init__(self, items: list[dict[str, Any]]):
        self._items = items
        self.calls: list[tuple[BatdongsanScrapeInput, int | None]] = []

    async def __call__(
        self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        self.calls.append((actor_input, limit))
        return {
            "items": self._items,
            "total_items": len(self._items),
            "degraded": False,
        }


@pytest.mark.asyncio
async def test_maps_input_and_wraps_items():
    scraper = _FakeScraper([{"listing_id": 1}, {"listing_id": 2}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(
        ScrapeInput(listing_type="buy", city="SG", district_id=1, max_items=5)
    )

    assert isinstance(out, ScrapeOutput)
    assert out.total_items == 2
    assert len(out.items) == 2
    assert out.items[0]["listing_id"] == 1
    assert out.degraded is False
    assert out.cost_micros == 2 * 3500

    actor_input, limit = scraper.calls[0]
    assert actor_input.listing_type == "buy"
    assert actor_input.city == "SG"
    assert actor_input.district_id == 1
    assert actor_input.max_items == 5
    assert limit == 5


@pytest.mark.asyncio
async def test_actor_exception_degrades_without_crashing():
    async def exploding_scraper(
        actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        raise RuntimeError("boom")

    execute = build_scrape_executor(scrape_fn=exploding_scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert isinstance(out, ScrapeOutput)
    assert out.total_items == 0
    assert out.items == []
    assert out.degraded is True
    assert out.degradation_reason == "api_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_rate_limited_actor_degrades_with_rate_limited_reason():
    async def limited_scraper(
        actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        raise BatdongsanRateLimitedError("429")

    execute = build_scrape_executor(scrape_fn=limited_scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_decode_error_actor_degrades_with_decode_error_reason():
    async def broken_scraper(
        actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        raise BatdongsanDecodeError("bad bytes")

    execute = build_scrape_executor(scrape_fn=broken_scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.degraded is True
    assert out.degradation_reason == "decode_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_blocked_actor_degrades_with_api_error_reason():
    async def blocked_scraper(
        actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        raise BatdongsanAccessBlockedError("blocked")

    execute = build_scrape_executor(scrape_fn=blocked_scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.degraded is True
    assert out.degradation_reason == "api_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_degraded_run_is_free():
    class _DegradedScraper(_FakeScraper):
        async def __call__(
            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
        ) -> dict[str, Any]:
            return {
                "items": self._items,
                "total_items": len(self._items),
                "degraded": True,
                "degradation_reason": "rate_limited",
            }

    scraper = _DegradedScraper([{"listing_id": 1}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.total_items == 1
    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_missing_degraded_key_defaults_to_false():
    class _NoDegradedScraper(_FakeScraper):
        async def __call__(
            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
        ) -> dict[str, Any]:
            return {"items": self._items, "total_items": len(self._items)}

    scraper = _NoDegradedScraper([{"listing_id": 1}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.total_items == 1
    assert out.degraded is False
    assert out.cost_micros == 1 * 3500


@pytest.mark.asyncio
async def test_none_result_degrades_with_unknown_reason():
    class _NoneScraper(_FakeScraper):
        async def __call__(
            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
        ) -> dict[str, Any] | None:
            return None

    execute = build_scrape_executor(scrape_fn=_NoneScraper([]))

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.total_items == 0
    assert out.degraded is True
    assert out.degradation_reason == "unknown"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_dict_without_total_items_counts_zero():
    class _NoCountScraper(_FakeScraper):
        async def __call__(
            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
        ) -> dict[str, Any]:
            return {"items": self._items}

    scraper = _NoCountScraper([{"listing_id": 1}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.total_items == 1
    assert out.degraded is False
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_dict_with_none_total_items_counts_zero():
    class _NoneCountScraper(_FakeScraper):
        async def __call__(
            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None, **kwargs: Any
        ) -> dict[str, Any]:
            return {"items": self._items, "total_items": None}

    scraper = _NoneCountScraper([{"listing_id": 1}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(city="HN", max_items=5))

    assert out.total_items == 1
    assert out.degraded is False
    assert out.cost_micros == 0
