"""``batdongsan.scrape`` executor: verb input → scraper → listings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.config import config
from app.proprietary.platforms.batdongsan import (
    BatdongsanScrapeOutput,
    scrape_batdongsan,
)
from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput

from .schemas import ScrapeInput, ScrapeOutput

ScrapeFn = Callable[..., Awaitable[BatdongsanScrapeOutput | dict[str, Any]]]


def _unwrap_result(result: BatdongsanScrapeOutput | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, BatdongsanScrapeOutput):
        return {
            "items": [item.to_output() for item in result.items],
            "total_items": result.total_items,
            "degraded": result.degraded,
            "degradation_reason": result.degradation_reason,
        }
    return result


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_batdongsan

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = BatdongsanScrapeInput(**payload.model_dump(exclude_unset=True))

        emit_progress(
            "starting",
            "Resolving Batdongsan targets",
            total=payload.max_items,
            unit="item",
        )
        raw = await scrape_fn(actor_input, limit=payload.max_items)
        result = _unwrap_result(raw)

        items = result["items"]
        total = result["total_items"]
        cost = total * getattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3500)

        emit_progress(
            "done",
            f"Scraped {total} item(s)",
            current=total,
            total=payload.max_items,
            unit="item",
        )
        return ScrapeOutput(
            items=items,
            cost_micros=cost,
            degraded=result.get("degraded", False),
            degradation_reason=result.get("degradation_reason"),
        )

    return execute
