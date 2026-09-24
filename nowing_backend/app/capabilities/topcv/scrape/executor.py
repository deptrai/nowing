"""``topcv.scrape`` executor: proxies to XActions via MCP (Story 40.2)."""

from __future__ import annotations

from uuid import uuid4

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.capabilities.core.xactions_proxy import make_xactions_executor
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
    """Return an executor that calls XActions via MCP.

    Story 40.2: Local browser scraping is replaced by the XActions gateway.
    The REST endpoint handles billing (gate_capability → charge_capability);
    this executor performs the x_scrape call and formats the response.
    """

    async def execute(
        input: ScrapeInput, ctx: CapabilityContext | None = None
    ) -> ScrapeOutput:
        emit_progress("fetching", "TopCV job search")

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

        # Anti-bot escalation still applies to XActions responses
        if not raw.get("next_action") and raw.get("degraded"):
            raw["next_action"] = _next_action(raw.get("degradation_reason"))
        if (
            raw.get("degraded")
            and raw.get("degradation_reason") in _BOT_DEGRADATION_REASONS
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
        return ScrapeOutput(**raw)

    return execute
