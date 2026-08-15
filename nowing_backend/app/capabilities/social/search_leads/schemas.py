"""Schemas for social lead search capability (Story 21.8 / AC 5)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SocialSearchLeadsInput(BaseModel):
    """Input payload for searching social leads."""

    platform: str | None = Field(
        default=None,
        description="Platform filter: 'facebook', 'twitter', or None for all",
    )
    intent: str | None = Field(
        default=None, description="Intent tag: 'sell', 'buy', 'hiring', 'seeking'"
    )
    keyword: str | None = Field(
        default=None, description="Search keyword in post content or author"
    )
    min_fit_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum lead fit score (0.0 to 1.0)"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Max number of items to return"
    )
    offset: int = Field(
        default=0, ge=0, description="Number of items to skip for pagination"
    )

    @property
    def estimated_units(self) -> int:
        return self.limit


class SocialPostItem(BaseModel):
    """Normalized social lead item with extracted contacts and intent."""

    platform: str
    external_post_id: str
    author_name: str | None = None
    author_url: str | None = None
    post_url: str | None = None
    content: str | None = None
    intent_tag: str | None = None
    fit_score: float = 0.0
    phones: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    prices: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    reactions_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    published_at: str | None = None


class SocialSearchLeadsOutput(BaseModel):
    """Output results for social lead search capability."""

    items: list[SocialPostItem] = Field(default_factory=list)
    total: int = 0
    cost_micros: int = 0
    degraded: bool = False
    degradation_reason: str | None = None
    next_action: str | None = None

    @property
    def billable_units(self) -> int:
        return len(self.items)
