"""LinkedIn Jobs Recruitment Capability Module."""

from __future__ import annotations

from app.capabilities.recruitment.linkedin_jobs.definition import (
    RECRUITMENT_SEARCH_LINKEDIN_JOBS,
)
from app.capabilities.recruitment.linkedin_jobs.executor import (
    build_linkedin_jobs_executor,
)
from app.capabilities.recruitment.linkedin_jobs.schemas import (
    CompanyGrowthSignal,
    LinkedInJobItem,
    LinkedInJobSearchInput,
    LinkedInJobSearchOutput,
)

__all__ = [
    "RECRUITMENT_SEARCH_LINKEDIN_JOBS",
    "CompanyGrowthSignal",
    "LinkedInJobItem",
    "LinkedInJobSearchInput",
    "LinkedInJobSearchOutput",
    "build_linkedin_jobs_executor",
]
