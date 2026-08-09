"""``muaban_bds.scrape`` executor: verb input → scraper → listings."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.proprietary.platforms.muaban_bds import (
    MuabanBdsScrapeOutput,
    scrape_muaban_bds,
)
from app.proprietary.platforms.muaban_bds.fetch import (
    MuabanBdsAccessBlockedError,
    MuabanBdsDecodeError,
    MuabanBdsRateLimitedError,
)
from app.proprietary.platforms.muaban_bds.schemas import MuabanBdsScrapeInput
from app.tasks.celery_tasks.anti_bot_escalation_tasks import (
    persist_anti_bot_escalation_task,
)

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[..., Awaitable[MuabanBdsScrapeOutput | dict[str, Any]]]

_BOT_DEGRADATION_REASONS = {
    "bot_detected",
    "rate_limited",
    "anti_bot_block",
    "access_blocked",
}

_DOMAIN = "muaban.net"


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
        capability="muaban_bds.scrape",
        domain=_DOMAIN,
        block_type=block_type,
    )


def _unwrap_result(
    result: MuabanBdsScrapeOutput | dict[str, Any] | None,
) -> dict[str, Any]:
    if result is None:
        return {
            "items": [],
            "total_items": 0,
            "degraded": True,
            "degradation_reason": "unknown",
        }
    if isinstance(result, MuabanBdsScrapeOutput):
        return {
            "items": [item.to_output() for item in result.items],
            "total_items": result.total_items,
            "degraded": result.degraded,
            "degradation_reason": result.degradation_reason,
        }
    return result


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_muaban_bds

    async def execute(
        payload: ScrapeInput, ctx: CapabilityContext | None = None
    ) -> ScrapeOutput:
        actor_input = MuabanBdsScrapeInput(**payload.model_dump(exclude_unset=True))

        emit_progress(
            "starting",
            "Resolving Muaban BĐS targets",
            total=payload.max_items,
            unit="item",
        )
        try:
            raw = await scrape_fn(actor_input, limit=payload.max_items)
        except MuabanBdsRateLimitedError:
            logger.exception("muaban_bds.scrape rate limited")
            _maybe_escalate(ctx, "rate_limited")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="rate_limited",
                next_action=_next_action("rate_limited"),
            )
        except MuabanBdsDecodeError:
            logger.exception("muaban_bds.scrape decode error")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="decode_error",
            )
        except MuabanBdsAccessBlockedError:
            logger.exception("muaban_bds.scrape access blocked")
            _maybe_escalate(ctx, "bot_detected")
            return ScrapeOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reason="bot_detected",
                next_action=_next_action("bot_detected"),
            )
        except Exception as exc:
            logger.exception("muaban_bds.scrape actor failed: %s", exc)
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
            cost = total * getattr(config, "MUABAN_BDS_SCRAPE_MICROS_PER_ITEM", 5500)

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
