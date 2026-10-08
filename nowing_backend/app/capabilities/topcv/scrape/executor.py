"""``topcv.scrape`` executor: proxies to XActions via MCP with local fallback."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import httpx

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.capabilities.core.xactions_proxy import make_xactions_executor
from app.config import config
from app.proprietary.platforms.topcv import scrape_topcv
from app.tasks.celery_tasks.anti_bot_escalation_tasks import (
    capture_platform_anti_bot_screenshot_task,
)

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_DOMAIN = "topcv.vn"

_BOT_DEGRADATION_REASONS = {
    "bot_detected",
    "rate_limited",
    "access_blocked",
}


def _next_action(degradation_reason: str | None) -> str | None:
    if degradation_reason in _BOT_DEGRADATION_REASONS:
        return "Escalated to human review; retry after credentials/proxy rotation"
    if degradation_reason == "api_error":
        return "TopCV search failed; proceed with alternative job sources"
    return None


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Return an executor that calls XActions via MCP with fallback to local scraper."""

    _scrape = scrape_fn or scrape_topcv

    async def execute(
        input: ScrapeInput, ctx: CapabilityContext | None = None
    ) -> ScrapeOutput:
        emit_progress("fetching", "TopCV job search")

        params = input.model_dump(exclude_none=True)
        items: list[dict[str, Any]] = []

        async def _local() -> dict[str, Any]:
            local_items: list[dict[str, Any]] = []
            for page in range(input.page, input.page + input.max_pages):
                remaining = input.max_items - len(local_items)
                if remaining <= 0:
                    break
                page_params = {
                    **params,
                    "page": page,
                    "max_pages": 1,
                    "max_items": remaining,
                }
                raw_local = await _scrape(page_params)
                if raw_local.get("degraded"):
                    return raw_local
                page_items = raw_local.get("items", [])
                if not page_items:
                    break
                local_items.extend(page_items)
                if len(local_items) >= input.max_items:
                    break
            return {"items": local_items, "degraded": False}

        raw: dict[str, Any] = {}
        try:
            proxy = make_xactions_executor(
                platform="topcv",
                action="search_jobs",
                args_mapper=lambda i: {
                    "keyword": i.keyword,
                    "location": i.location,
                    "salary_min": i.salary_min,
                    "salary_max": i.salary_max,
                    "employment_type": i.employment_type,
                    "page": i.page,
                    "max_pages": i.max_pages,
                    "max_items": i.max_items,
                },
            )
            raw = await proxy(input, ctx)
        except Exception as exc:
            logger.warning(
                "XActions topcv search failed (%s); falling back to local scraper",
                exc,
            )
            try:
                raw = await _local()
            except (Exception, httpx.HTTPError) as local_exc:
                logger.warning("Local topcv scraper failed: %s", local_exc)
                return ScrapeOutput(
                    items=[],
                    cost_micros=0,
                    degraded=True,
                    degradation_reason="api_error",
                    next_action=_next_action("api_error"),
                )

        if isinstance(raw, dict) and raw.get("degraded"):
            # Anti-bot escalation applies to degraded responses
            if (
                raw.get("degradation_reason") in _BOT_DEGRADATION_REASONS
            ):
                run_id = (
                    ctx.run_id
                    if ctx is not None and ctx.run_id is not None
                    else str(uuid4())
                )
                workspace_id = (
                    ctx.workspace_id
                    if ctx is not None and ctx.workspace_id is not None
                    else 0
                )
                capture_platform_anti_bot_screenshot_task.delay(
                    url=f"https://{_DOMAIN}",
                    run_id=run_id,
                    workspace_id=workspace_id,
                    capability="topcv.scrape",
                    domain=_DOMAIN,
                    block_type=raw.get("degradation_reason") or "UNKNOWN",
                )
            return ScrapeOutput(
                items=raw.get("items", []),
                cost_micros=0,
                degraded=True,
                degradation_reason=raw.get("degradation_reason"),
                next_action=raw.get("next_action")
                or _next_action(raw.get("degradation_reason")),
            )

        items = (raw.get("items", []) if isinstance(raw, dict) else raw)[
            : input.max_items
        ]
        cost_micros = len(items) * getattr(config, "TOPCV_SCRAPE_MICROS_PER_ITEM", 0)
        emit_progress(
            "done",
            "TopCV job search complete",
            current=len(items),
            total=input.max_items,
            unit="item",
        )
        return ScrapeOutput(
            items=items,
            cost_micros=cost_micros,
            degraded=False,
            degradation_reason=None,
            next_action=None,
        )

    return execute
