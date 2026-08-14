"""Unit tests for the ``chotot_bds.scrape`` executor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.capabilities.chotot.scrape.executor import (
    _maybe_escalate,
    _next_action,
    _unwrap_result,
    build_scrape_executor,
)
from app.capabilities.chotot.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.platforms.chotot import CategoryConfigError
from app.proprietary.platforms.chotot.fetch import (
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
)
from app.proprietary.platforms.chotot.schemas import (
    ChototBdsScrapeInput,
    ChototListing,
    ChototScrapeOutput,
)

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


def test_next_action_returns_escalation_for_bot_reasons():
    assert _next_action("bot_detected") is not None
    assert _next_action("rate_limited") is not None
    assert _next_action("api_error") is None
    assert _next_action(None) is None


def test_maybe_escalate_is_noop_without_context():
    assert _maybe_escalate(None, "bot_detected") is None


def test_unwrap_result_defaults_to_empty_degraded():
    default = _unwrap_result(None)
    assert default == {
        "items": [],
        "total_items": 0,
        "degraded": True,
        "degradation_reason": "unknown",
    }


def test_unwrap_result_unwraps_pydantic_model():
    item = ChototListing(listing_id=1, title="x", category="cars")
    out = ChototScrapeOutput(
        items=[item], total_items=1, degraded=False, degradation_reason=None
    )
    assert _unwrap_result(out) == {
        "items": [item.to_output()],
        "total_items": 1,
        "billable_units": 1,
        "degraded": False,
        "degradation_reason": None,
    }


@pytest.mark.asyncio
async def test_degraded_result_cost_is_zero():
    async def degraded_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        return {
            "items": [{"listing_id": 1, "category": "cars"}],
            "total_items": 1,
            "billable_units": 1,
            "degraded": True,
            "degradation_reason": "bot_detected",
        }

    execute = build_scrape_executor(scrape_fn=degraded_scraper)
    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.degraded is True
    assert out.cost_micros == 0
    assert out.next_action is not None


@pytest.mark.asyncio
async def test_invalid_category_returns_zero_cost():
    async def bad_category(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        raise CategoryConfigError("nope")

    execute = build_scrape_executor(scrape_fn=bad_category)
    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.degraded is True
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_total_items_none_becomes_zero():
    """A None total_items must be coerced to 0, not crash or default to 1."""

    async def null_total(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        return {
            "items": [],
            "total_items": None,
            "billable_units": 0,
            "degraded": False,
        }

    execute = build_scrape_executor(scrape_fn=null_total)
    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.total_items == 0
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_total_items_and_billable_fallback_when_absent():
    """If the scraper omits both total_items and billable_units, cost must be zero.

    This kills NumberReplacer mutants that change the default ``.get(..., 0)``
    to a non-zero value, which would incorrectly bill for items.
    """

    async def partial_scraper(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        return {
            "items": [{"listing_id": 1, "category": "cars"}],
        }

    execute = build_scrape_executor(scrape_fn=partial_scraper)
    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.billable_units == 1
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_uses_default_rate_when_config_missing():
    """If config does not define the rate attribute, executor should still bill 3500."""

    async def one_item(
        actor_input: ChototBdsScrapeInput, *, limit: int | None = None
    ) -> dict[str, Any]:
        return {
            "items": [{"listing_id": 1, "category": "cars"}],
            "total_items": 1,
            "billable_units": 1,
            "degraded": False,
        }

    execute = build_scrape_executor(
        scrape_fn=one_item, rate_attr="MISSING_RATE_ATTR_XYZ"
    )
    out = await execute(ScrapeInput(city="hanoi", max_items=5))

    assert out.cost_micros == 1 * 3500
