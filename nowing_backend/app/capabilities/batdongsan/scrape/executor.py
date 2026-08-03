"""``batdongsan.scrape`` executor: verb input → scraper → listings."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.config import config
from app.proprietary.platforms.batdongsan import (
    BatdongsanScrapeOutput,
    scrape_batdongsan,
)
from app.proprietary.platforms.batdongsan.fetch import (
    BatdongsanAccessBlockedError,
    BatdongsanDecodeError,
    BatdongsanRateLimitedError,
)
from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[..., Awaitable[BatdongsanScrapeOutput | dict[str, Any]]]


def _unwrap_result(
    result: BatdongsanScrapeOutput | dict[str, Any] | None,
) -> dict[str, Any]:
    if result is None:
        return {
            "items": [],
            "total_items": 0,
            "degraded": True,
            "degradation_reason": "unknown",
        }
    if isinstance(result, BatdongsanScrapeOutput):
        return {
            "items": [item.to_output() for item in result.items],
            "total_items": result.total_items,
            "degraded": result.degraded,
            "degradation_reason": result.degradation_reason,
        }
    return result


def build_scrape_executor(
    scrape_fn: ScrapeFn | None = None,
    web_fetch_fn: ScrapeFn | None = None,
) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_batdongsan
    web_fetch_fn = web_fetch_fn

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = BatdongsanScrapeInput(**payload.model_dump(exclude_unset=True))

        emit_progress(
            "starting",
            "Resolving Batdongsan targets",
            total=payload.max_items,
            unit="item",
        )
        try:
            kwargs: dict[str, Any] = {
                "limit": payload.max_items,
                "resolve_phones": payload.resolve_phones,
            }
            if web_fetch_fn is not None:
                kwargs["web_fetch_fn"] = web_fetch_fn
            raw = await scrape_fn(actor_input, **kwargs)
        except BatdongsanRateLimitedError:
            logger.exception("batdongsan.scrape rate limited")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="rate_limited",
            )
        except BatdongsanDecodeError:
            logger.exception("batdongsan.scrape decode error")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="decode_error",
            )
        except (BatdongsanAccessBlockedError, Exception) as exc:
            logger.exception("batdongsan.scrape actor failed: %s", exc)
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="api_error",
            )
        result = _unwrap_result(raw)

        items = result.get("items", []) or []
        total_raw = result.get("total_items", 0)
        total = int(total_raw) if total_raw is not None else 0
        degraded = bool(result.get("degraded", False))
        if degraded:
            cost = 0
        else:
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
            degraded=degraded,
            degradation_reason=result.get("degradation_reason"),
        )

    return execute
