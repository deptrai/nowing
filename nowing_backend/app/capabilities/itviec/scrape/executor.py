"""``itviec.scrape`` executor: verb input → HTML parser → job listings."""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.itviec import scrape_itviec

from .schemas import ScrapeInput, ScrapeOutput


def build_scrape_executor() -> Executor:
    """Return an executor that calls the ITviec proprietary fetcher."""

    async def execute(input: ScrapeInput) -> ScrapeOutput:
        await emit_progress("fetching", "ITviec job search")
        raw = await scrape_itviec(input.model_dump())
        return ScrapeOutput(**raw)

    return execute
