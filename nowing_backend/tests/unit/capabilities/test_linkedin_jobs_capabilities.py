"""Unit tests for LinkedIn Recruitment Job Search Capability (Story 12.10 / AC 4 / AD-LI-6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.core import get_capability
from app.capabilities.recruitment.linkedin_jobs.definition import (
    RECRUITMENT_SEARCH_LINKEDIN_JOBS,
)
from app.capabilities.recruitment.linkedin_jobs.schemas import (
    LinkedInJobSearchInput,
    LinkedInJobSearchOutput,
)
from app.mcp_tools import MCP_TOOL_CATALOG, McpToolGroup
from app.proprietary.platforms.linkedin.guest_job_scraper import LinkedInJobPosting


def test_mcp_tool_catalog_contains_recruitment_search_linkedin_jobs() -> None:
    """AC 4 & AD-LI-6: Ensure nowing_recruitment_search_linkedin_jobs is in catalog."""
    matching = [
        t for t in MCP_TOOL_CATALOG if t["name"] == "nowing_recruitment_search_linkedin_jobs"
    ]
    assert len(matching) == 1
    assert matching[0]["group"] in (McpToolGroup.SCRAPER, McpToolGroup.LEAD_INTELLIGENCE)


def test_recruitment_search_linkedin_jobs_capability_registered() -> None:
    """Ensure capability recruitment.linkedin_jobs is registered in store."""
    cap = get_capability("recruitment.linkedin_jobs")
    assert cap is not None
    assert cap.name == "recruitment.linkedin_jobs"
    assert cap.input_schema == LinkedInJobSearchInput
    assert cap.output_schema == LinkedInJobSearchOutput


@pytest.mark.asyncio
async def test_recruitment_search_linkedin_jobs_executor_flow() -> None:
    """AC 4: Capability executor queries scraper, computes velocity, filters intent."""
    now = datetime.now(UTC)
    mock_postings = [
        LinkedInJobPosting(
            job_id="job-1",
            title="Senior Python Architect",
            company_name="Vingroup",
            company_slug="vingroup",
            location="Hanoi, Vietnam",
            workplace_type="Hybrid",
            seniority_level="Director",
            employment_type="Full-time",
            description_text="Leading architecture...",
            skills=["Python", "System Design"],
            posted_at=now - timedelta(days=3),
            source_url="https://vn.linkedin.com/jobs/view/job-1",
        ),
        LinkedInJobPosting(
            job_id="job-2",
            title="Junior PHP Dev",
            company_name="LegacyCorp",
            company_slug="legacycorp",
            location="Hanoi, Vietnam",
            workplace_type="On-site",
            seniority_level="Entry",
            employment_type="Full-time",
            description_text="Maintenance work...",
            skills=["PHP"],
            posted_at=now - timedelta(days=45),  # prior period
            source_url="https://vn.linkedin.com/jobs/view/job-2",
        ),
    ]

    with patch(
        "app.capabilities.recruitment.linkedin_jobs.executor.LinkedInGuestJobScraper.search_jobs",
        new=AsyncMock(return_value=mock_postings),
    ):
        input_payload = LinkedInJobSearchInput(
            keyword="Python",
            location="Vietnam",
            limit=10,
            min_growth_rate=0.0,
            filter_high_intent=False,
        )

        output: LinkedInJobSearchOutput = await RECRUITMENT_SEARCH_LINKEDIN_JOBS.executor(
            input_payload
        )

        assert output.total_found == 2
        assert len(output.jobs) == 2
        assert output.jobs[0].company_name == "Vingroup"
        assert output.jobs[0].high_buying_intent is True
        assert output.jobs[0].company_growth_rate >= 0.20


@pytest.mark.asyncio
async def test_recruitment_search_linkedin_jobs_executor_filtered() -> None:
    """AC 4: Capability executor filters only high buying intent when requested."""
    now = datetime.now(UTC)
    mock_postings = [
        LinkedInJobPosting(
            job_id="job-1",
            title="Senior Python Architect",
            company_name="Vingroup",
            company_slug="vingroup",
            posted_at=now - timedelta(days=3),
        ),
        LinkedInJobPosting(
            job_id="job-2",
            title="Junior Dev",
            company_name="LegacyCorp",
            company_slug="legacycorp",
            posted_at=now - timedelta(days=45),
        ),
    ]

    with patch(
        "app.capabilities.recruitment.linkedin_jobs.executor.LinkedInGuestJobScraper.search_jobs",
        new=AsyncMock(return_value=mock_postings),
    ):
        input_payload = LinkedInJobSearchInput(
            keyword="Python",
            location="Vietnam",
            limit=10,
            filter_high_intent=True,
        )

        output: LinkedInJobSearchOutput = await RECRUITMENT_SEARCH_LINKEDIN_JOBS.executor(
            input_payload
        )

        # LegacyCorp had no jobs in last 30d (only prior 45d), so Vingroup is high intent
        assert len(output.jobs) == 1
        assert output.jobs[0].company_name == "Vingroup"
        assert output.jobs[0].high_buying_intent is True
