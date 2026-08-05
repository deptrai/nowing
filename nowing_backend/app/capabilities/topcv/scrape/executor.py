"""``topcv.scrape`` executor: verb input → anti-bot fetcher → job listings."""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.topcv import scrape_topcv

from .schemas import ScrapeInput, ScrapeOutput


def build_scrape_executor() -> Executor:
    """Return an executor that calls the TopCV proprietary fetcher."""

    async def execute(input: ScrapeInput) -> ScrapeOutput:
        emit_progress("fetching", "TopCV job search")
        raw = await scrape_topcv(input.model_dump())
        return ScrapeOutput(**raw)

    return execute
