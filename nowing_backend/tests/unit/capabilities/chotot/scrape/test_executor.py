"""Unit tests for the ``chotot_bds.scrape`` executor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.capabilities.chotot.scrape.executor import build_scrape_executor
from app.capabilities.chotot.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.platforms.chotot.fetch import (
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
)
from app.proprietary.platforms.chotot.schemas import ChototBdsScrapeInput

pytestmark = pytest.mark.unit

ScrapeFn = Callable[..., Awaitable[dict[str, Any]]]


class _FakeScraper:
    """Records the actor input it was called with; returns canned output."""

    def __init__(self, items: list[dict[str, Any]]):
        self._items = items
        self.calls: list[tuple[ChototBdsScrapeInput, int | None]] = []

    async def __call__(
        self, actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        self.calls.append((actor_input, limit))
        return {
            "items": self._items,
            "total_items": len(self._items),
            "billable_units": sum(
                1 for it in self._items if it.get("category") and it["category"] != "unknown"
            ),
            "degraded": False,
        }


@pytest.mark.asyncio
async def test_maps_input_and_wraps_items():
    scraper = _FakeScraper(
        [{"listing_id": 1, "category": "bds"}, {"listing_id": 2, "category": "bds"}]
    )
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(
        ScrapeInput(listing_type="buy", city="ho chi minh", max_items=5)
    )

    assert isinstance(out, ScrapeOutput)
    assert out.total_items == 2
    assert len(out.items) == 2
    assert out.degraded is False
    assert out.cost_micros == 2 * 3500

    actor_input, limit = scraper.calls[0]
    assert actor_input.listing_type == "buy"
    assert actor_input.city == "ho chi minh"
    assert actor_input.max_items == 5
    assert limit == 5


@pytest.mark.asyncio
async def test_actor_exception_degrades_without_crashing():
    async def exploding_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        raise RuntimeError("boom")

    execute = build_scrape_executor(scrape_fn=exploding_scraper)

    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert isinstance(out, ScrapeOutput)
    assert out.total_items == 0
    assert out.items == []
    assert out.degraded is True
    assert out.degradation_reason == "api_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_rate_limited_actor_degrades_with_rate_limited_reason():
    async def limited_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        raise ChototBdsRateLimitedError("429")

    execute = build_scrape_executor(scrape_fn=limited_scraper)

    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_decode_error_actor_degrades_with_decode_error_reason():
    async def broken_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        raise ChototBdsDecodeError("bad json")

    execute = build_scrape_executor(scrape_fn=broken_scraper)

    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.degraded is True
    assert out.degradation_reason == "decode_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_bot_detected_actor_degrades_with_bot_detected_reason():
    from app.proprietary.platforms.chotot.fetch import ChototBdsBotDetectedError

    async def blocked_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        raise ChototBdsBotDetectedError("403")

    execute = build_scrape_executor(scrape_fn=blocked_scraper)

    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.degraded is True
    assert out.degradation_reason == "bot_detected"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_bds_executor_uses_bds_rate_config():
    """The deprecated bds alias should compute cost_micros from the BĐS rate."""

    async def bds_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        return {
            "items": [{"listing_id": 1, "category": "bds"}],
            "total_items": 1,
            "billable_units": 1,
            "degraded": False,
        }

    execute = build_scrape_executor(
        scrape_fn=bds_scraper,
        rate_attr="CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM",
    )

    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.cost_micros == 1 * 3500


@pytest.mark.asyncio
async def test_bds_executor_locks_category_to_bds():
    """The deprecated bds alias must ignore user-supplied category and use 'bds'."""

    captured: list[ChototBdsScrapeInput] = []

    async def recording_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        captured.append(actor_input)
        return {
            "items": [{"listing_id": 1, "category": "bds"}],
            "total_items": 1,
            "billable_units": 1,
            "degraded": False,
        }

    execute = build_scrape_executor(
        scrape_fn=recording_scraper,
        rate_attr="CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM",
        locked_category="bds",
    )

    out = await execute(
        ScrapeInput(category="cars", city="ho chi minh", max_items=5)
    )

    assert captured[0].category == "bds"
    assert out.category == "cars"  # output preserves caller category for traceability


@pytest.mark.asyncio
async def test_all_unknown_category_listings_cost_zero():
    scraper = _FakeScraper(
        [
            {"listing_id": 1, "category": "unknown"},
            {"listing_id": 2, "category": "unknown"},
        ]
    )
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(category="electronics", city="hanoi", max_items=5))

    assert out.total_items == 2
    assert out.billable_units == 0
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_unknown_category_listings_are_not_billed():
    scraper = _FakeScraper(
        [
            {"listing_id": 1, "category": "bds"},
            {"listing_id": 2, "category": "unknown"},
        ]
    )
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(category="electronics", city="hanoi", max_items=5))

    assert out.total_items == 2
    assert out.billable_units == 1
    assert out.cost_micros == 1 * 3500
