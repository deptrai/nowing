"""``walmart.reviews`` executor: verb input → scraper → review items."""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.walmart import scrape_walmart_reviews

from .schemas import ReviewsInput, ReviewsOutput


def build_reviews_executor() -> Executor:
    """Return an executor that calls the Walmart reviews scraper."""

    async def execute(input: ReviewsInput) -> ReviewsOutput:
        emit_progress("fetching", "Walmart reviews")
        raw = await scrape_walmart_reviews(input.model_dump())
        return ReviewsOutput(**raw)

    return execute
