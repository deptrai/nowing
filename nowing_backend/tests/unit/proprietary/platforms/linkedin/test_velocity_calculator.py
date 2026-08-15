"""Unit tests for LinkedIn Hiring Velocity Calculator (Story 12.10 / AC 3 / AD-LI-3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.proprietary.platforms.linkedin.guest_job_scraper import LinkedInJobPosting
from app.proprietary.platforms.linkedin.velocity_calculator import (
    HiringVelocityCalculator,
    calculate_hiring_velocity,
    enrich_jobs_with_velocity,
)


def test_calculate_hiring_velocity_formula() -> None:
    """AC 3: Verify hiring velocity math and high buying intent flag (>= 20%)."""
    # 20% growth
    metrics_20pct = calculate_hiring_velocity(
        company_name="Vingroup",
        company_slug="vingroup",
        jobs_last_30d=12,
        jobs_prior_30d=10,
    )
    assert metrics_20pct.jobs_last_30d == 12
    assert metrics_20pct.jobs_prior_30d == 10
    assert metrics_20pct.hiring_velocity_30d == pytest.approx(0.20, abs=1e-3)
    assert metrics_20pct.high_buying_intent is True

    # 50% growth
    metrics_50pct = calculate_hiring_velocity(
        company_name="FPT Software",
        company_slug="fpt-software",
        jobs_last_30d=15,
        jobs_prior_30d=10,
    )
    assert metrics_50pct.hiring_velocity_30d == pytest.approx(0.50, abs=1e-3)
    assert metrics_50pct.high_buying_intent is True

    # Negative / stagnant growth (10% growth < 20%)
    metrics_10pct = calculate_hiring_velocity(
        company_name="Viettel",
        company_slug="viettel",
        jobs_last_30d=11,
        jobs_prior_30d=10,
    )
    assert metrics_10pct.hiring_velocity_30d == pytest.approx(0.10, abs=1e-3)
    assert metrics_10pct.high_buying_intent is False

    # Decline
    metrics_decline = calculate_hiring_velocity(
        company_name="OldCorp",
        company_slug="oldcorp",
        jobs_last_30d=4,
        jobs_prior_30d=8,
    )
    assert metrics_decline.hiring_velocity_30d == pytest.approx(-0.50, abs=1e-3)
    assert metrics_decline.high_buying_intent is False

    # New expansion with zero prior postings
    metrics_fresh = calculate_hiring_velocity(
        company_name="Startup Unicorn",
        company_slug="startup-unicorn",
        jobs_last_30d=5,
        jobs_prior_30d=0,
    )
    assert metrics_fresh.hiring_velocity_30d == pytest.approx(5.0, abs=1e-3)
    assert metrics_fresh.high_buying_intent is True


def test_calculate_company_velocity_from_postings() -> None:
    """AC 3: Computes aggregate velocity across companies from posting time distribution."""
    now = datetime.now(UTC)
    calc = HiringVelocityCalculator()

    postings = [
        # Company A: 3 jobs in last 30d, 1 job in prior 30d -> growth = (3-1)/1 = 200% >= 20%
        LinkedInJobPosting(
            job_id="job-a1",
            title="Backend Dev",
            company_name="Company A",
            company_slug="comp-a",
            posted_at=now - timedelta(days=5),
        ),
        LinkedInJobPosting(
            job_id="job-a2",
            title="Frontend Dev",
            company_name="Company A",
            company_slug="comp-a",
            posted_at=now - timedelta(days=15),
        ),
        LinkedInJobPosting(
            job_id="job-a3",
            title="DevOps Engineer",
            company_name="Company A",
            company_slug="comp-a",
            posted_at=now - timedelta(days=25),
        ),
        LinkedInJobPosting(
            job_id="job-a4",
            title="Legacy QA",
            company_name="Company A",
            company_slug="comp-a",
            posted_at=now - timedelta(days=40),  # prior 30d
        ),
        # Company B: 1 job in last 30d, 2 jobs in prior 30d -> growth = (1-2)/2 = -50%
        LinkedInJobPosting(
            job_id="job-b1",
            title="Accountant",
            company_name="Company B",
            company_slug="comp-b",
            posted_at=now - timedelta(days=10),
        ),
        LinkedInJobPosting(
            job_id="job-b2",
            title="Old HR",
            company_name="Company B",
            company_slug="comp-b",
            posted_at=now - timedelta(days=35),
        ),
        LinkedInJobPosting(
            job_id="job-b3",
            title="Old Admin",
            company_name="Company B",
            company_slug="comp-b",
            posted_at=now - timedelta(days=45),
        ),
    ]

    summaries = calc.calculate_from_postings(postings, reference_time=now)
    assert len(summaries) == 2

    comp_a_metric = summaries["comp-a"]
    assert comp_a_metric.jobs_last_30d == 3
    assert comp_a_metric.jobs_prior_30d == 1
    assert comp_a_metric.hiring_velocity_30d == pytest.approx(2.0, abs=1e-3)
    assert comp_a_metric.high_buying_intent is True

    comp_b_metric = summaries["comp-b"]
    assert comp_b_metric.jobs_last_30d == 1
    assert comp_b_metric.jobs_prior_30d == 2
    assert comp_b_metric.hiring_velocity_30d == pytest.approx(-0.5, abs=1e-3)
    assert comp_b_metric.high_buying_intent is False


def test_enrich_jobs_with_velocity() -> None:
    """AC 4: Enriches job records with company velocity metrics."""
    now = datetime.now(UTC)
    postings = [
        LinkedInJobPosting(
            job_id="job-1",
            title="AI Engineer",
            company_name="TechCorp",
            company_slug="techcorp",
            posted_at=now - timedelta(days=2),
        ),
        LinkedInJobPosting(
            job_id="job-2",
            title="Data Scientist",
            company_name="TechCorp",
            company_slug="techcorp",
            posted_at=now - timedelta(days=10),
        ),
    ]

    enriched = enrich_jobs_with_velocity(postings, reference_time=now)
    assert len(enriched) == 2
    assert enriched[0].company_active_jobs == 2
    assert enriched[0].high_buying_intent is True
    assert enriched[0].company_growth_rate >= 0.20
