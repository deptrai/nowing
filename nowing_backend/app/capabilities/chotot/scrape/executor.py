"""``chotot.scrape`` executor: verb input -> multi-category scraper -> listings."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.proprietary.platforms.chotot import (
    CategoryConfigError,
    ChototBdsAccessBlockedError,
    ChototBdsBotDetectedError,
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
    ChototScrapeInput,
    ChototScrapeOutput,
    scrape_chotot,
)
from app.tasks.celery_tasks.anti_bot_escalation_tasks import (
    capture_platform_anti_bot_screenshot_task,
)

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[..., Awaitable[ChototScrapeOutput]]

_BOT_DEGRADATION_REASONS = {
    "bot_detected",
    "rate_limited",
    "anti_bot_block",
    "access_blocked",
}

_DOMAIN = "chotot.com"


def _next_action(degradation_reason: str | None) -> str | None:
    if degradation_reason in _BOT_DEGRADATION_REASONS:
        return "Escalated to human review; retry after credentials/proxy rotation"
    return None


def _maybe_escalate(
    ctx: CapabilityContext | None,
    block_type: str,
    url: str | None = None,
) -> None:
    if ctx is None or ctx.run_id is None:
        return
    capture_platform_anti_bot_screenshot_task.delay(
        url=url or f"https://{_DOMAIN}",
        run_id=ctx.run_id,
        workspace_id=ctx.workspace_id,
        capability="chotot.scrape",
        domain=_DOMAIN,
        block_type=block_type,
    )


def _unwrap_result(
    result: ChototScrapeOutput | dict[str, Any] | None,
) -> dict[str, Any]:
    if result is None:
        return {
            "items": [],
            "total_items": 0,
            "degraded": True,
            "degradation_reason": "unknown",
        }
    if isinstance(result, ChototScrapeOutput):
        return {
            "items": [item.to_output() for item in result.items],
            "total_items": result.total_items,
            "billable_units": result.billable_units,
            "degraded": result.degraded,
            "degradation_reason": result.degradation_reason,
        }
    return result


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Callable[..., Awaitable[ScrapeOutput]]:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_chotot

    async def execute(
        payload: ScrapeInput, ctx: CapabilityContext | None = None
    ) -> ScrapeOutput:
        actor_input = ChototScrapeInput(**payload.model_dump())

        emit_progress(
            "starting",
            f"Resolving Chợ Tốt listings for {actor_input.category}",
            total=payload.max_items,
            unit="item",
        )
        try:
            raw = await scrape_fn(actor_input, limit=payload.max_items)
        except ChototBdsRateLimitedError:
            logger.exception("chotot.scrape rate limited")
            _maybe_escalate(ctx, "rate_limited")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="rate_limited",
                next_action=_next_action("rate_limited"),
                category=payload.category,
            )
        except ChototBdsDecodeError:
            logger.exception("chotot.scrape decode error")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="decode_error",
                category=payload.category,
            )
        except ChototBdsBotDetectedError:
            logger.exception("chotot.scrape bot detected")
            _maybe_escalate(ctx, "bot_detected")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="bot_detected",
                next_action=_next_action("bot_detected"),
                category=payload.category,
            )
        except ChototBdsAccessBlockedError:
            logger.exception("chotot.scrape access blocked")
            _maybe_escalate(ctx, "bot_detected")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="bot_detected",
                next_action=_next_action("bot_detected"),
                category=payload.category,
            )
        except CategoryConfigError as exc:
            logger.exception("chotot.scrape invalid category: %s", exc)
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason=f"invalid_input: {exc}",
                category=payload.category,
            )
        except Exception as exc:
            logger.exception("chotot.scrape actor failed: %s", exc)
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="api_error",
                category=payload.category,
            )

        result = _unwrap_result(raw)
        items = result.get("items", []) or []
        total_raw = result.get("total_items", 0)
        total = int(total_raw) if total_raw is not None else 0
        billable = result.get("billable_units") or total
        billable = int(billable) if isinstance(billable, (int, float)) else total
        degraded = bool(result.get("degraded", False))
        if degraded:
            _maybe_escalate(ctx, result.get("degradation_reason") or "UNKNOWN")
            cost = 0
        else:
            cost = billable * getattr(config, "CHOTOT_SCRAPE_MICROS_PER_ITEM", 3500)

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
            next_action=result.get("next_action")
            or _next_action(result.get("degradation_reason")),
            category=payload.category,
        )

    return execute
