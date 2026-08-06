"""``walmart.scrape`` executor: verb input → scraper → product listings."""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.walmart import scrape_walmart

from .schemas import ScrapeInput, ScrapeOutput


def build_scrape_executor() -> Executor:
    """Return an executor that calls the Walmart proprietary scraper."""

    async def execute(input: ScrapeInput) -> ScrapeOutput:
        emit_progress("fetching", "Walmart product search")
        raw = await scrape_walmart(input.model_dump())
        return ScrapeOutput(**raw)

    return execute
