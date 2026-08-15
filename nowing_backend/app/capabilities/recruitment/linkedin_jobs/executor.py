"""Executor for LinkedIn Recruitment Job Search Capability (Story 12.10 / AD-LI-6)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.recruitment.linkedin_jobs.schemas import (
    CompanyGrowthSignal,
    LinkedInJobItem,
    LinkedInJobSearchInput,
    LinkedInJobSearchOutput,
)
from app.proprietary.platforms.linkedin.guest_job_scraper import (
    LinkedInGuestJobScraper,
    LinkedInJobPosting,
    persist_linkedin_jobs,
)
from app.proprietary.platforms.linkedin.velocity_calculator import (
    HiringVelocityCalculator,
    enrich_jobs_with_velocity,
)

logger = logging.getLogger(__name__)

ScraperFn = Callable[..., Awaitable[list[LinkedInJobPosting]]]


def build_linkedin_jobs_executor(
    scraper_fn: ScraperFn | None = None,
    velocity_calculator: HiringVelocityCalculator | None = None,
) -> Executor:
    """Build capability executor function for LinkedIn job search and hiring velocity analysis."""

    async def execute(payload: LinkedInJobSearchInput) -> LinkedInJobSearchOutput:
        emit_progress(
            "starting",
            f"Searching LinkedIn jobs for '{payload.keyword or payload.company_slug}' in {payload.location}",
            total=payload.limit,
            unit="job",
        )

        calc = velocity_calculator or HiringVelocityCalculator()

        if scraper_fn:
            postings = await scraper_fn(
                keyword=payload.keyword,
                location=payload.location,
                company_slug=payload.company_slug,
                limit=payload.limit,
                fetch_details=payload.fetch_details,
            )
        else:
            scraper = LinkedInGuestJobScraper()
            postings = await scraper.search_jobs(
                keyword=payload.keyword,
                location=payload.location,
                company_slug=payload.company_slug,
                limit=payload.limit,
                fetch_details=payload.fetch_details,
            )

        # Compute company hiring velocity metrics
        company_metrics = calc.calculate_from_postings(postings)

        # Enrich job records
        enriched_jobs = enrich_jobs_with_velocity(
            postings, metrics_by_company=company_metrics
        )

        # Filter by minimum growth rate or high intent flag
        filtered_jobs: list[LinkedInJobItem] = []
        for job in enriched_jobs:
            if payload.filter_high_intent and not job.high_buying_intent:
                continue
            if payload.min_growth_rate > 0 and job.company_growth_rate < payload.min_growth_rate:
                continue
            filtered_jobs.append(job)

        growth_signals = [
            CompanyGrowthSignal(
                company_name=m.company_name,
                company_slug=m.company_slug,
                active_jobs_count=m.active_jobs_count,
                jobs_last_30d=m.jobs_last_30d,
                jobs_prior_30d=m.jobs_prior_30d,
                hiring_velocity_30d=m.hiring_velocity_30d,
                high_buying_intent=m.high_buying_intent,
            )
            for m in company_metrics.values()
            if (not payload.filter_high_intent or m.high_buying_intent)
            and (payload.min_growth_rate <= 0 or m.hiring_velocity_30d >= payload.min_growth_rate)
        ]

        # Optional DB persistence
        if payload.persist_to_db and postings:
            try:
                from app.db import get_db

                async for session in get_db():
                    await persist_linkedin_jobs(postings, session=session)
                    break
            except Exception as exc:
                logger.warning(f"Failed to persist LinkedIn jobs to database: {exc}")

        emit_progress(
            "done",
            f"Found {len(filtered_jobs)} matching LinkedIn jobs across {len(growth_signals)} companies",
            current=len(filtered_jobs),
            unit="job",
        )

        return LinkedInJobSearchOutput(
            keyword=payload.keyword,
            location=payload.location,
            jobs=filtered_jobs,
            company_growth_signals=growth_signals,
            total_found=len(filtered_jobs),
        )

    return execute
