"""``itviec.scrape`` executor: verb input → HTML parser → job listings."""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.itviec import scrape_itviec

from .schemas import ScrapeInput, ScrapeOutput

_BOT_DEGRADATION_REASONS = {
    "bot_detected",
    "rate_limited",
    "anti_bot_block",
    "access_blocked",
}


def _next_action(degradation_reason: str | None) -> str | None:
    if degradation_reason in _BOT_DEGRADATION_REASONS:
        return "Escalated to human review; retry after credentials/proxy rotation"
    return None


def build_scrape_executor() -> Executor:
    """Return an executor that calls the ITviec proprietary fetcher."""

    async def execute(input: ScrapeInput) -> ScrapeOutput:
        emit_progress("fetching", "ITviec job search")
        raw = await scrape_itviec(input.model_dump())
        if not raw.get("next_action") and raw.get("degraded"):
            raw["next_action"] = _next_action(raw.get("degradation_reason"))
        return ScrapeOutput(**raw)

    return execute
