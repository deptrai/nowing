"""Schemas for B2B Decision Maker Capability (Story 21.9 / AD-LI-6)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class B2BDecisionMakerInput(BaseModel):
    """Input payload for looking up company decision makers."""

    company_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Target company name (e.g., 'FPT Software', 'Vingroup')",
    )
    domain: str | None = Field(
        default=None,
        description="Target company web domain (e.g., 'fpt-software.com')",
    )
    roles: list[str] | None = Field(
        default=None,
        description="Target roles filter (e.g. ['CEO', 'Founder', 'HR Director', 'CTO'])",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum executive profiles to discover",
    )


class ExecutiveDecisionMakerItem(BaseModel):
    """Normalized executive decision maker record."""

    full_name: str
    title: str | None = None
    company_name: str
    linkedin_url: str
    linkedin_slug: str
    email_prediction: str | None = None
    inferred_emails: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    verified_mx: bool = False


class B2BDecisionMakerOutput(BaseModel):
    """Output payload returning verified executive decision makers."""

    company_name: str
    domain: str | None = None
    executives: list[ExecutiveDecisionMakerItem] = Field(default_factory=list)
    total_found: int = 0
