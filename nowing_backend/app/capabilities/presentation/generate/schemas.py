"""Pydantic schemas for presentation.generate capability (Story 27.2a)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import config as app_config


class PresentationCapabilityInput(BaseModel):
    """Input parameters for presentation.generate capability."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="Natural language description of the slide deck",
    )
    workspace_id: int = Field(..., description="Owning workspace ID")
    output_format: str = Field(
        default="pptx",
        pattern=r"^(pptx|marp)$",
        description="Output format: pptx or marp",
    )
    language: str = Field(
        default="en",
        max_length=10,
        description="Target UI language (en, vi)",
    )
    user_id: UUID | None = Field(default=None, description="Requesting user ID")

    @field_validator("prompt")
    @classmethod
    def validate_prompt_length(cls, v: str) -> str:
        max_chars = app_config.PRESENTATION_MAX_PROMPT_CHARS
        if len(v) > max_chars:
            raise ValueError(
                f"Prompt exceeds maximum allowed length of {max_chars} characters (got {len(v)})"
            )
        return v


class PresentationCapabilityOutput(BaseModel):
    """Output results of presentation.generate capability."""

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

    model_config = ConfigDict(arbitrary_types_allowed=False)
