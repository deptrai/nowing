"""Unit tests for the ``muaban_bds.scrape`` executor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.capabilities.muaban_bds.scrape.executor import build_scrape_executor
from app.capabilities.muaban_bds.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.platforms.muaban_bds.schemas import MuabanBdsScrapeInput

pytestmark = pytest.mark.unit

ScrapeFn = Callable[..., Awaitable[dict[str, Any]]]


class _FakeScraper:
    """Records the actor input it was called with; returns canned output."""

    def __init__(self, items: list[dict[str, Any]]):
        self._items = items
        self.calls: list[tuple[MuabanBdsScrapeInput, int | None]] = []

    async def __call__(
        self, actor_input: MuabanBdsScrapeInput, *, limit: int | None = None
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
    executor = build_scrape_executor(scrape_fn=scraper)

    payload = ScrapeInput(
        listing_type="buy",
        property_type="house",
        city="ho-chi-minh",
        district="Quận 1",
        max_items=5,
    )
    result = await executor(payload)

    assert isinstance(result, ScrapeOutput)
    assert result.items == [{"listing_id": 1}, {"listing_id": 2}]
    assert result.cost_micros > 0
    assert not result.degraded

    assert len(scraper.calls) == 1
    actor_input, limit = scraper.calls[0]
    assert isinstance(actor_input, MuabanBdsScrapeInput)
    assert actor_input.city == "ho-chi-minh"
    assert actor_input.property_type == "house"
    assert limit == 5


@pytest.mark.asyncio
async def test_degraded_run_costs_zero():
    class _DegradedScraper:
        async def __call__(self, actor_input, *, limit=None):
            return {
                "items": [],
                "total_items": 0,
                "degraded": True,
                "degradation_reason": "rate_limited",
            }

    executor = build_scrape_executor(scrape_fn=_DegradedScraper())
    result = await executor(ScrapeInput(max_items=5))
    assert result.degraded
    assert result.cost_micros == 0
    assert result.degradation_reason == "rate_limited"
