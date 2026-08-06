"""``indeed.scrape`` executor: verb input → anti-bot fetcher → job listings."""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.indeed import scrape_indeed

from .schemas import ScrapeInput, ScrapeOutput


def build_scrape_executor() -> Executor:
    """Return an executor that calls the Indeed proprietary fetcher."""

    async def execute(input: ScrapeInput) -> ScrapeOutput:
        emit_progress("fetching", "Indeed job search")
        raw = await scrape_indeed(input.model_dump())
        return ScrapeOutput(**raw)

    return execute
