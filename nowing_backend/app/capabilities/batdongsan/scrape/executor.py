"""``batdongsan.scrape`` executor: verb input → scraper → listings."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
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
from app.tasks.celery_tasks.anti_bot_escalation_tasks import (
    persist_anti_bot_escalation_task,
)

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[..., Awaitable[BatdongsanScrapeOutput | dict[str, Any]]]

_BOT_DEGRADATION_REASONS = {
    "bot_detected",
    "rate_limited",
    "anti_bot_block",
    "access_blocked",
}

_DOMAIN = "batdongsan.com.vn"


def _next_action(degradation_reason: str | None) -> str | None:
    if degradation_reason in _BOT_DEGRADATION_REASONS:
        return "Escalated to human review; retry after credentials/proxy rotation"
    return None


def _maybe_escalate(
    ctx: CapabilityContext | None,
    block_type: str,
) -> None:
    if ctx is None or ctx.run_id is None:
        return
    persist_anti_bot_escalation_task.delay(
        screenshot_png_b64=None,
        run_id=ctx.run_id,
        workspace_id=ctx.workspace_id,
        capability="batdongsan.scrape",
        domain=_DOMAIN,
        block_type=block_type,
    )


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
            "next_action": getattr(result, "next_action", None),
        }
    return result


def build_scrape_executor(
    scrape_fn: ScrapeFn | None = None,
    web_fetch_fn: ScrapeFn | None = None,
) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_batdongsan
    web_fetch_fn = web_fetch_fn

    async def execute(
        payload: ScrapeInput, ctx: CapabilityContext | None = None
    ) -> ScrapeOutput:
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
            _maybe_escalate(ctx, "rate_limited")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="rate_limited",
                next_action="Escalated to human review; retry after credentials/proxy rotation",
            )
        except BatdongsanDecodeError:
            logger.exception("batdongsan.scrape decode error")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="decode_error",
            )
        except BatdongsanAccessBlockedError as exc:
            logger.exception("batdongsan.scrape access blocked: %s", exc)
            _maybe_escalate(ctx, "bot_detected")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="bot_detected",
                next_action="Escalated to human review; retry after credentials/proxy rotation",
            )
        except Exception as exc:
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
            _maybe_escalate(
                ctx, result.get("degradation_reason") or "UNKNOWN"
            )
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
            next_action=result.get("next_action")
            or _next_action(result.get("degradation_reason")),
        )

    return execute
