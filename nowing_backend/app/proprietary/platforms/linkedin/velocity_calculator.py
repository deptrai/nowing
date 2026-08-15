"""LinkedIn Headcount Growth Signal & Hiring Velocity Calculator (Story 12.10 / AC 3 / AD-LI-3).

Computes 30-day hiring velocity and expansion buying intent signals.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import LinkedinCompany, LinkedinJob
from app.proprietary.platforms.linkedin.schemas import (
    LinkedInJobItem,
    LinkedInJobPosting,
)

logger = logging.getLogger(__name__)

# Minimum growth rate threshold to trigger high buying intent signal (20%)
BUYING_INTENT_GROWTH_THRESHOLD: float = 0.20


class CompanyVelocityMetrics(BaseModel):
    """30-Day Hiring Velocity and Intent Score for a Company."""

    company_name: str
    company_slug: str
    active_jobs_count: int = 0
    jobs_last_30d: int = 0
    jobs_prior_30d: int = 0
    hiring_velocity_30d: float = 0.0
    high_buying_intent: bool = False


def calculate_hiring_velocity(
    company_name: str,
    company_slug: str,
    jobs_last_30d: int,
    jobs_prior_30d: int,
) -> CompanyVelocityMetrics:
    """Calculate 30-day hiring velocity and high buying intent flag (AD-LI-3).

    Formula:
        If both 0 -> 0.0
        If prior is 0 and last > 0 -> velocity = float(last)
        Else -> (last - prior) / max(prior, 1)

    Buying Intent:
        Growth rate >= 20% (0.20) and at least 1 recent job posting.
    """
    if jobs_last_30d <= 0 and jobs_prior_30d <= 0:
        velocity = 0.0
    elif jobs_prior_30d <= 0:
        velocity = float(jobs_last_30d)
    else:
        velocity = (jobs_last_30d - jobs_prior_30d) / max(jobs_prior_30d, 1)

    high_intent = (velocity >= BUYING_INTENT_GROWTH_THRESHOLD) and (jobs_last_30d > 0)
    active_count = max(jobs_last_30d, 0)

    return CompanyVelocityMetrics(
        company_name=company_name,
        company_slug=company_slug,
        active_jobs_count=active_count,
        jobs_last_30d=jobs_last_30d,
        jobs_prior_30d=jobs_prior_30d,
        hiring_velocity_30d=round(velocity, 4),
        high_buying_intent=high_intent,
    )


class HiringVelocityCalculator:
    """Engine for computing company headcount signals from LinkedIn job datasets."""

    def calculate_from_postings(
        self,
        postings: list[LinkedInJobPosting],
        reference_time: datetime | None = None,
    ) -> dict[str, CompanyVelocityMetrics]:
        """Aggregate job postings by company and compute 30-day velocity metrics."""
        now = reference_time or datetime.now(UTC)
        cutoff_30d = now - timedelta(days=30)
        cutoff_60d = now - timedelta(days=60)

        # Company mapping: slug -> {name, last_30d, prior_30d}
        company_stats: dict[str, dict[str, Any]] = {}

        for job in postings:
            slug = job.company_slug or "unknown"
            if slug not in company_stats:
                company_stats[slug] = {
                    "company_name": job.company_name,
                    "jobs_last_30d": 0,
                    "jobs_prior_30d": 0,
                }

            dt = job.posted_at
            if dt is not None and dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)

            if dt is None:
                # Default to recent window if unspecified
                company_stats[slug]["jobs_last_30d"] += 1
            elif dt >= cutoff_30d:
                company_stats[slug]["jobs_last_30d"] += 1
            elif dt >= cutoff_60d:
                company_stats[slug]["jobs_prior_30d"] += 1

        results: dict[str, CompanyVelocityMetrics] = {}
        for slug, stats in company_stats.items():
            metrics = calculate_hiring_velocity(
                company_name=stats["company_name"],
                company_slug=slug,
                jobs_last_30d=stats["jobs_last_30d"],
                jobs_prior_30d=stats["jobs_prior_30d"],
            )
            results[slug] = metrics

        return results

    async def calculate_from_db(
        self,
        session: AsyncSession,
        company_slugs: list[str] | None = None,
        reference_time: datetime | None = None,
    ) -> dict[str, CompanyVelocityMetrics]:
        """Compute velocity metrics directly from PostgreSQL `linkedin_jobs` table in a single query."""
        now = reference_time or datetime.now(UTC)
        cutoff_30d = now - timedelta(days=30)
        cutoff_60d = now - timedelta(days=60)

        # Single grouped query with conditional aggregation to eliminate N+1 round trips
        from sqlalchemy import case

        stmt = (
            select(
                LinkedinCompany.company_slug,
                LinkedinCompany.company_name,
                func.count(case((LinkedinJob.posted_at >= cutoff_30d, 1))).label("count_last"),
                func.count(
                    case(
                        (
                            (LinkedinJob.posted_at >= cutoff_60d)
                            & (LinkedinJob.posted_at < cutoff_30d),
                            1,
                        )
                    )
                ).label("count_prior"),
            )
            .outerjoin(LinkedinJob, LinkedinJob.company_id == LinkedinCompany.id)
            .group_by(
                LinkedinCompany.company_slug,
                LinkedinCompany.company_name,
            )
        )
        if company_slugs:
            stmt = stmt.where(LinkedinCompany.company_slug.in_(company_slugs))

        comp_res = await session.execute(stmt)
        rows = comp_res.all()

        results: dict[str, CompanyVelocityMetrics] = {}
        for row in rows:
            slug, name, count_last, count_prior = row
            metrics = calculate_hiring_velocity(
                company_name=name,
                company_slug=slug,
                jobs_last_30d=count_last or 0,
                jobs_prior_30d=count_prior or 0,
            )
            results[slug] = metrics

        return results


def enrich_jobs_with_velocity(
    jobs: list[LinkedInJobPosting],
    reference_time: datetime | None = None,
    metrics_by_company: dict[str, CompanyVelocityMetrics] | None = None,
) -> list[LinkedInJobItem]:
    """Enrich raw LinkedIn job postings with company hiring velocity metrics."""
    if metrics_by_company is None:
        calc = HiringVelocityCalculator()
        metrics_by_company = calc.calculate_from_postings(jobs, reference_time=reference_time)

    enriched_items: list[LinkedInJobItem] = []
    for job in jobs:
        slug = job.company_slug or "unknown"
        metrics = metrics_by_company.get(slug)

        active_jobs = metrics.active_jobs_count if metrics else 1
        growth_rate = metrics.hiring_velocity_30d if metrics else 0.0
        high_intent = metrics.high_buying_intent if metrics else False

        item = LinkedInJobItem(
            job_id=job.job_id,
            title=job.title,
            company_name=job.company_name,
            company_slug=job.company_slug,
            location=job.location,
            workplace_type=job.workplace_type,
            seniority_level=job.seniority_level,
            employment_type=job.employment_type,
            description_text=job.description_text,
            skills=job.skills,
            posted_at=job.posted_at,
            source_url=job.source_url,
            company_active_jobs=active_jobs,
            company_growth_rate=growth_rate,
            high_buying_intent=high_intent,
        )
        enriched_items.append(item)

    return enriched_items
