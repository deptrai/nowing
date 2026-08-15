"""Registration of the ``recruitment.linkedin_jobs`` capability (Story 12.10 / AD-LI-6)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.recruitment.linkedin_jobs.executor import (
    build_linkedin_jobs_executor,
)
from app.capabilities.recruitment.linkedin_jobs.schemas import (
    LinkedInJobSearchInput,
    LinkedInJobSearchOutput,
)

RECRUITMENT_SEARCH_LINKEDIN_JOBS = Capability(
    name="recruitment.linkedin_jobs",
    description="Search public LinkedIn job postings and track 30-day company headcount hiring growth velocity.",
    input_schema=LinkedInJobSearchInput,
    output_schema=LinkedInJobSearchOutput,
    executor=build_linkedin_jobs_executor(),
    billing_unit=None,
    docs_url="/docs/recruitment/linkedin-jobs",
)

register_capability(RECRUITMENT_SEARCH_LINKEDIN_JOBS)
