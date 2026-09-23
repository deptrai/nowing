"""``topcv.scrape`` executor: verb input → anti-bot fetcher → job listings."""

from __future__ import annotations

from uuid import uuid4

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.proprietary.platforms.topcv import scrape_topcv
from app.tasks.celery_tasks.anti_bot_escalation_tasks import (
    capture_platform_anti_bot_screenshot_task,
)

from .schemas import ScrapeInput, ScrapeOutput

_DOMAIN = "topcv.vn"

_BOT_DEGRADATION_REASONS = {
    "bot_detected",
    "rate_limited",
    "access_blocked",
}


def _next_action(degradation_reason: str | None) -> str | None:
    if degradation_reason in _BOT_DEGRADATION_REASONS:
        return "Escalated to human review; retry after credentials/proxy rotation"
    return None


def build_scrape_executor() -> Executor:
    """Return an executor that calls the TopCV proprietary fetcher."""

    async def execute(
        input: ScrapeInput, ctx: CapabilityContext | None = None
    ) -> ScrapeOutput:
        emit_progress("fetching", "TopCV job search")
        raw = await scrape_topcv(input.model_dump())
        if not raw.get("next_action") and raw.get("degraded"):
            raw["next_action"] = _next_action(raw.get("degradation_reason"))
        if (
            raw.get("degraded")
            and raw.get("degradation_reason") in _BOT_DEGRADATION_REASONS
        ):
            # Story 12-2, Item 5: Un-gate anti-bot escalation when ctx or ctx.run_id is None
            # (e.g. in sync REST or direct agent tool invocations). Use a valid fallback UUID.
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
        return ScrapeOutput(**raw)

    return execute
