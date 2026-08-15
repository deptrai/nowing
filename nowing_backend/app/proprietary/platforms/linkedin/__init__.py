"""LinkedIn Platform Scraper & B2B Intelligence Module (Story 12.10 & 21.9 / AD-LI-1 to AD-LI-7)."""

from __future__ import annotations

from app.proprietary.platforms.linkedin.executive_dorker import (
    ExecutiveDorker,
    dork_executives,
)
from app.proprietary.platforms.linkedin.executive_parser import (
    ExecutiveParser,
    parse_linkedin_slug,
    parse_serp_title_and_snippet,
)
from app.proprietary.platforms.linkedin.guest_job_scraper import (
    LinkedInGuestJobScraper,
    LinkedInJobPosting,
    parse_guest_job_cards,
    parse_guest_job_detail,
    persist_linkedin_jobs,
)
from app.proprietary.platforms.linkedin.query_builder import build_serp_dork_query
from app.proprietary.platforms.linkedin.schemas import (
    DEFAULT_EXECUTIVE_ROLES,
    CompanyGrowthSignal,
    ExecutiveDorkInput,
    ExecutiveDorkResult,
    ExecutiveProfile,
    LinkedInJobItem,
    LinkedInJobSearchInput,
    LinkedInJobSearchOutput,
)
from app.proprietary.platforms.linkedin.velocity_calculator import (
    CompanyVelocityMetrics,
    HiringVelocityCalculator,
    calculate_hiring_velocity,
    enrich_jobs_with_velocity,
)

__all__ = [
    "DEFAULT_EXECUTIVE_ROLES",
    "CompanyGrowthSignal",
    "CompanyVelocityMetrics",
    "ExecutiveDorkInput",
    "ExecutiveDorkResult",
    "ExecutiveDorker",
    "ExecutiveParser",
    "ExecutiveProfile",
    "HiringVelocityCalculator",
    "LinkedInGuestJobScraper",
    "LinkedInJobItem",
    "LinkedInJobPosting",
    "LinkedInJobSearchInput",
    "LinkedInJobSearchOutput",
    "build_serp_dork_query",
    "calculate_hiring_velocity",
    "dork_executives",
    "enrich_jobs_with_velocity",
    "parse_guest_job_cards",
    "parse_guest_job_detail",
    "parse_linkedin_slug",
    "parse_serp_title_and_snippet",
    "persist_linkedin_jobs",
]
