"""Pydantic schemas for LinkedIn platform scraper, jobs, and executive intelligence (Story 12.10 & 21.9)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_EXECUTIVE_ROLES: list[str] = [
    "CEO",
    "Founder",
    "Co-Founder",
    "Managing Director",
    "HR Director",
    "Chief Human Resources Officer",
    "CTO",
    "CFO",
    "COO",
    "VP of Engineering",
    "Director",
]


class ExecutiveProfile(BaseModel):
    """Normalized executive decision maker profile."""

    full_name: str = Field(..., description="Full name of the executive")
    title: str | None = Field(default=None, description="Current job title / position")
    company_name: str = Field(..., description="Target company name")
    linkedin_url: str = Field(..., description="Public LinkedIn profile URL")
    linkedin_slug: str = Field(..., description="Clean LinkedIn profile slug/identifier")
    department: str | None = Field(default="Executive Leadership", description="Inferred department")
    inferred_emails: list[str] = Field(default_factory=list, description="Candidate corporate emails")
    email_prediction: str | None = Field(default=None, description="Highest-probability inferred email")
    confidence_score: float = Field(default=0.7, description="Confidence score from 0.0 to 1.0")
    verified_mx: bool = Field(default=False, description="Whether domain MX DNS check passed")
    source_query: str | None = Field(default=None, description="SERP query string used to discover")
    raw_metadata: dict[str, Any] = Field(default_factory=dict, description="Raw snippet/meta extracted")


class ExecutiveDorkInput(BaseModel):
    """Input parameters for SERP dorking executive search."""

    company_name: str = Field(..., min_length=1, max_length=255, description="Target company name")
    domain: str | None = Field(default=None, description="Corporate website domain (e.g. example.com)")
    roles: list[str] | None = Field(default=None, description="Executive role keywords filter")
    country_code: str = Field(default="vn", description="Target country code (e.g., vn, us, sg)")
    limit: int = Field(default=10, ge=1, le=50, description="Max executive profiles to retrieve")


class ExecutiveDorkResult(BaseModel):
    """Structured result of executive search operation."""

    company_name: str
    domain: str | None = None
    executives: list[ExecutiveProfile] = Field(default_factory=list)
    query_used: str
    total_found: int = 0


# ============================================================================
# LinkedIn Jobs & Headcount Growth Signal Schemas (Story 12.10)
# ============================================================================


class LinkedInJobPosting(BaseModel):
    """Normalized raw LinkedIn job posting parsed from Guest API."""

    job_id: str = Field(..., description="Unique LinkedIn Job ID")
    title: str = Field(..., description="Job Title")
    company_name: str = Field(default="Unknown Company", description="Employer company name")
    company_slug: str = Field(default="unknown-company", description="Employer LinkedIn slug")
    location: str = Field(default="Vietnam", description="Job location or country")
    workplace_type: str | None = Field(default=None, description="Workplace type: On-site, Hybrid, Remote")
    seniority_level: str | None = Field(default=None, description="Seniority: Entry level, Mid-Senior, Director")
    employment_type: str | None = Field(default=None, description="Employment type: Full-time, Contract, Part-time")
    description_text: str = Field(default="", description="Job description plain text")
    skills: list[str] = Field(default_factory=list, description="Extracted skill keywords")
    posted_at: datetime | None = Field(default=None, description="Job posting timestamp (UTC)")
    source_url: str = Field(default="", description="Public LinkedIn job posting URL")
    raw_entities: dict[str, Any] = Field(default_factory=dict, description="Raw entity attributes from scraper")


class CompanyGrowthSignal(BaseModel):
    """Company 30-day hiring velocity and expansion buying intent score."""

    company_name: str
    company_slug: str
    active_jobs_count: int = 0
    jobs_last_30d: int = 0
    jobs_prior_30d: int = 0
    hiring_velocity_30d: float = 0.0
    high_buying_intent: bool = False


class LinkedInJobItem(BaseModel):
    """Enriched job posting item including hiring velocity indicators."""

    job_id: str
    title: str
    company_name: str
    company_slug: str
    location: str
    workplace_type: str | None = None
    seniority_level: str | None = None
    employment_type: str | None = None
    description_text: str = ""
    skills: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    source_url: str = ""
    company_active_jobs: int = 0
    company_growth_rate: float = 0.0
    high_buying_intent: bool = False


class LinkedInJobSearchInput(BaseModel):
    """Input payload for searching LinkedIn jobs & detecting hiring signals."""

    keyword: str = Field(
        default="",
        description="Search keyword (e.g., 'Python', 'AI Engineer', 'Sales Director')",
    )
    location: str = Field(
        default="Vietnam",
        description="Target location or country (e.g., 'Vietnam', 'Hanoi', 'Ho Chi Minh')",
    )
    company_slug: str | None = Field(
        default=None,
        description="Optional LinkedIn company slug filter (e.g. 'vingroup', 'fpt-software')",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum job postings to return",
    )
    min_growth_rate: float = Field(
        default=0.0,
        description="Minimum 30-day hiring velocity growth rate filter (e.g., 0.20 for 20%)",
    )
    filter_high_intent: bool = Field(
        default=False,
        description="If True, only return jobs from companies with high buying intent (>=20% growth)",
    )
    fetch_details: bool = Field(
        default=False,
        description="Whether to fetch individual job detail pages for complete descriptions",
    )
    persist_to_db: bool = Field(
        default=False,
        description="Whether to persist scraped jobs and companies to PostgreSQL idempotently",
    )


class LinkedInJobSearchOutput(BaseModel):
    """Output payload returning enriched jobs with hiring growth metrics."""

    keyword: str
    location: str
    jobs: list[LinkedInJobItem] = Field(default_factory=list)
    company_growth_signals: list[CompanyGrowthSignal] = Field(default_factory=list)
    total_found: int = 0
