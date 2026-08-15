"""Schemas for LinkedIn Recruitment Job Search Capability (Story 12.10 / AD-LI-6)."""

from __future__ import annotations

from app.proprietary.platforms.linkedin.schemas import (
    CompanyGrowthSignal,
    LinkedInJobItem,
    LinkedInJobSearchInput,
    LinkedInJobSearchOutput,
)

__all__ = [
    "CompanyGrowthSignal",
    "LinkedInJobItem",
    "LinkedInJobSearchInput",
    "LinkedInJobSearchOutput",
]
