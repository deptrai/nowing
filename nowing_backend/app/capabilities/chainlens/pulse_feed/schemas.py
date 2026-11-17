"""Schemas for chainlens.pulse_feed capability (Story 20.10)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PulseItem(BaseModel):
    id: str
    title: str
    summary: str
    url: str | None = None
    source: str | None = None
    topic: str = "general"
    published_at: str | None = Field(None, alias="publishedAt")
    has_angles: bool = Field(False, alias="hasAngles")


class PulsePagination(BaseModel):
    next_cursor: str | None = Field(None, alias="nextCursor")
    has_more: bool = Field(False, alias="hasMore")
    limit: int = 20


class PulseFeedInput(BaseModel):
    """Input parameters for pulling the curated intelligence feed."""

    topic: str = Field(
        "all",
        pattern="^(all|tech|ai|finance|science|security|startup)$",
        description="Filter feed by category topic",
    )
    cursor: str | None = Field(
        None,
        description="ISO datetime cursor for keyset pagination (older-than)",
    )
    limit: int = Field(20, ge=1, le=50)


class PulseFeedOutput(BaseModel):
    """Curated intelligence feed output."""

    items: list[PulseItem] = Field(default_factory=list)
    pagination: PulsePagination = Field(default_factory=PulsePagination)


class PulseAngleResponse(BaseModel):
    """Pre-generated research angle for a pulse feed item."""

    angle_id: str = Field(..., alias="angleId")
    label: str
    description: str
    prompt: str
    estimated_credits: int = Field(1, alias="estimatedCredits")
    cost_dollars: float = Field(0.01, alias="costDollars")
    model: str = "claude-haiku-4.5"
