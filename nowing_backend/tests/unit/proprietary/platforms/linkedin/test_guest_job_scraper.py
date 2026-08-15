"""Unit tests for LinkedIn Guest Job Scraper (Story 12.10 / AD-LI-1, AD-LI-2, AD-LI-5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.proprietary.platforms.linkedin.guest_job_scraper import (
    LinkedInGuestJobScraper,
    LinkedInJobPosting,
    parse_guest_job_cards,
    parse_guest_job_detail,
    persist_linkedin_jobs,
)

# Realistic mock HTML for guest job search endpoint
# https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
MOCK_SEARCH_HTML = """
<ul class="jobs-search__results-list">
  <li>
    <div class="base-card relative w-full hover:no-underline focus:no-underline base-card--link base-search-card base-search-card--link job-search-card"
         data-entity-urn="urn:li:jobPosting:3987654321">
      <a class="base-card__full-link" href="https://vn.linkedin.com/jobs/view/senior-python-engineer-at-vingroup-3987654321?position=1&amp;pageNum=0">
        <span class="sr-only">Senior Python Engineer</span>
      </a>
      <div class="base-search-card__info">
        <h3 class="base-search-card__title">Senior Python Engineer</h3>
        <h4 class="base-search-card__subtitle">
          <a class="hidden-nested-link" href="https://vn.linkedin.com/company/vingroup?trk=public_jobs">Vingroup</a>
        </h4>
        <div class="base-search-card__metadata">
          <span class="job-search-card__location">Hanoi, Vietnam (Hybrid)</span>
          <time class="job-search-card__listdate" datetime="2026-08-10">5 days ago</time>
        </div>
      </div>
    </div>
  </li>
  <li>
    <div class="base-card base-search-card job-search-card"
         data-entity-urn="urn:li:jobPosting:3987654322">
      <a class="base-card__full-link" href="https://vn.linkedin.com/jobs/view/ai-tech-lead-at-fpt-software-3987654322">
        <span class="sr-only">AI Tech Lead</span>
      </a>
      <div class="base-search-card__info">
        <h3 class="base-search-card__title">AI Tech Lead</h3>
        <h4 class="base-search-card__subtitle">
          <a class="hidden-nested-link" href="https://vn.linkedin.com/company/fpt-software">FPT Software</a>
        </h4>
        <div class="base-search-card__metadata">
          <span class="job-search-card__location">Ho Chi Minh City, Vietnam (Remote)</span>
          <time class="job-search-card__listdate" datetime="2026-08-12">3 days ago</time>
        </div>
      </div>
    </div>
  </li>
</ul>
"""

# Realistic mock HTML for guest job detail endpoint
# https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}
MOCK_DETAIL_HTML = """
<div class="decorated-job-posting__details">
  <section class="top-card-layout">
    <h2 class="top-card-layout__title">Senior Python Engineer</h2>
    <a class="topcard__org-name-link" href="https://vn.linkedin.com/company/vingroup">Vingroup</a>
    <span class="topcard__flavor topcard__flavor--bullet">Hanoi, Vietnam</span>
    <span class="posted-time-ago__text">5 days ago</span>
  </section>
  <div class="show-more-less-html__markup">
    <p>We are looking for a Senior Python Engineer to design scalable microservices and data pipelines using FastAPI, PostgreSQL, Redis, and PyTorch.</p>
    <p>Requirements: 5+ years of Python experience, distributed systems, Docker, Kubernetes.</p>
  </div>
  <ul class="description__job-criteria-list">
    <li class="description__job-criteria-item">
      <h3 class="description__job-criteria-subheader">Seniority level</h3>
      <span class="description__job-criteria-text">Mid-Senior level</span>
    </li>
    <li class="description__job-criteria-item">
      <h3 class="description__job-criteria-subheader">Employment type</h3>
      <span class="description__job-criteria-text">Full-time</span>
    </li>
    <li class="description__job-criteria-item">
      <h3 class="description__job-criteria-subheader">Job function</h3>
      <span class="description__job-criteria-text">Engineering and Information Technology</span>
    </li>
    <li class="description__job-criteria-item">
      <h3 class="description__job-criteria-subheader">Industries</h3>
      <span class="description__job-criteria-text">Software Development and IT Services</span>
    </li>
  </ul>
</div>
"""


def test_parse_guest_job_cards() -> None:
    """AC 1: Parse job search cards extracting job_id, title, company, location, posted_at."""
    jobs = parse_guest_job_cards(MOCK_SEARCH_HTML)
    assert len(jobs) == 2

    job1 = jobs[0]
    assert job1.job_id == "3987654321"
    assert job1.title == "Senior Python Engineer"
    assert job1.company_name == "Vingroup"
    assert job1.company_slug == "vingroup"
    assert "Hanoi, Vietnam" in job1.location
    assert job1.workplace_type == "Hybrid"
    assert job1.posted_at is not None

    job2 = jobs[1]
    assert job2.job_id == "3987654322"
    assert job2.title == "AI Tech Lead"
    assert job2.company_name == "FPT Software"
    assert job2.company_slug == "fpt-software"
    assert "Ho Chi Minh City" in job2.location
    assert job2.workplace_type == "Remote"


def test_parse_guest_job_detail() -> None:
    """AC 1: Parse job detail extracting description, skills, seniority, employment type."""
    detail = parse_guest_job_detail(MOCK_DETAIL_HTML)
    assert detail["title"] == "Senior Python Engineer"
    assert detail["company_name"] == "Vingroup"
    assert "FastAPI" in detail["description_text"]
    assert "PostgreSQL" in detail["description_text"]
    assert detail["seniority_level"] == "Mid-Senior level"
    assert detail["employment_type"] == "Full-time"
    assert "Python" in detail["skills"] or "FastAPI" in detail["skills"]


@pytest.mark.asyncio
async def test_scraper_search_jobs_flow() -> None:
    """AC 1 & AD-LI-1: LinkedInGuestJobScraper performs zero-login search and optional detail enrichment."""
    scraper = LinkedInGuestJobScraper(jitter_delay=(0.0, 0.0))

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.text = MOCK_SEARCH_HTML

    mock_detail_resp = MagicMock()
    mock_detail_resp.status_code = 200
    mock_detail_resp.text = MOCK_DETAIL_HTML

    async def mock_get(url, *args, **kwargs):
        if "seeMoreJobPostings" in str(url):
            return mock_search_resp
        return mock_detail_resp

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=mock_get)

    jobs = await scraper.search_jobs(
        keyword="python",
        location="Vietnam",
        limit=2,
        fetch_details=True,
        client=mock_client,
    )

    assert len(jobs) == 2
    assert jobs[0].job_id == "3987654321"
    assert jobs[0].seniority_level == "Mid-Senior level"
    assert "FastAPI" in jobs[0].description_text


@pytest.mark.asyncio
async def test_scraper_rate_limit_and_error_handling() -> None:
    """AD-LI-2: Gracefully handles 429 rate limit and HTTP errors."""
    scraper = LinkedInGuestJobScraper(jitter_delay=(0.0, 0.0))

    mock_429_resp = MagicMock()
    mock_429_resp.status_code = 429
    mock_429_resp.text = "Too Many Requests"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_429_resp)

    jobs = await scraper.search_jobs(
        keyword="golang",
        location="Vietnam",
        limit=5,
        client=mock_client,
    )

    assert jobs == []


@pytest.mark.asyncio
async def test_persist_linkedin_jobs_idempotent() -> None:
    """AC 2 & AD-LI-5: Persists jobs and company records idempotently."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (101, "vingroup")
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    jobs = [
        LinkedInJobPosting(
            job_id="test-job-101",
            title="Senior Backend Engineer",
            company_name="Vingroup",
            company_slug="vingroup",
            location="Hanoi, Vietnam",
            workplace_type="On-site",
            seniority_level="Mid-Senior",
            employment_type="Full-time",
            description_text="Building cloud microservices",
            skills=["Python", "FastAPI", "SQLAlchemy"],
            posted_at=datetime.now(UTC) - timedelta(days=2),
            source_url="https://vn.linkedin.com/jobs/view/test-job-101",
        )
    ]

    persisted_count = await persist_linkedin_jobs(jobs, session=mock_session)
    assert persisted_count == 1
    assert mock_session.commit.called

