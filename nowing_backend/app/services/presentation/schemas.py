"""Pydantic schemas for Presentation Studio (Story 27.2a)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.config import config as app_config


class ChartSpec(BaseModel):
    """Optional chart data for a slide."""

    categories: list[str] = Field(default_factory=list)
    series: list[float | int] = Field(default_factory=list)


class SlideSpec(BaseModel):
    """One slide in the generated deck."""

    title: str = Field(..., max_length=255)
    bullets: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)
    chart: ChartSpec | None = Field(default=None)


class DeckSpec(BaseModel):
    """Structured LLM output for a slide deck."""

    title: str = Field(..., max_length=255)
    slug: str | None = Field(default=None, max_length=63)
    description: str | None = Field(default=None, max_length=1000)
    slides: list[SlideSpec] = Field(..., min_length=1)


class GeneratePresentationInput(BaseModel):
    """Input payload for generating a slide deck."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=app_config.PRESENTATION_MAX_PROMPT_CHARS,
        description="Natural language description of the slide deck",
    )
    output_format: str = Field(
        default="pptx",
        pattern=r"^(pptx|marp)$",
        description="Output format: pptx or marp",
    )
    workspace_id: int = Field(..., description="Owning workspace ID")
    user_id: UUID | None = Field(default=None, description="Requesting user ID")
    language: str = Field(
        default="en",
        max_length=10,
        description="Target UI language (e.g. en, vi)",
    )


class GeneratePresentationOutput(BaseModel):
    """Output payload after generating a slide deck."""

    status: str = Field(
        ...,
        max_length=50,
        description="Status: generating, ready, failed, degraded, validation_failed",
    )
    presentation_id: str | None = Field(default=None, max_length=36)
    workspace_id: int | None = None
    title: str | None = Field(default=None, max_length=255)
    slug: str | None = Field(default=None, max_length=63)
    format: str | None = Field(default=None, max_length=10)
    slide_count: int | None = None
    file_path: str | None = None
    download_url: str | None = Field(default=None, max_length=512)
    preview_url: str | None = Field(default=None, max_length=512)
    error: str | None = Field(default=None, max_length=1000)
    degradation_reason: str | None = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(arbitrary_types_allowed=False)


class SlidePresentationRead(BaseModel):
    """Public read schema for a SlidePresentation entity."""

    id: str
    workspace_id: int
    user_id: UUID | None = None
    title: str
    slug: str
    format: str
    status: str
    slide_count: int | None = None
    preview_url: str | None = None
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    degradation_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)
