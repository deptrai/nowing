"""Pydantic schemas for web_builder.build_app capability (Story 27.1, AC-5)."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.config import config as app_config


class WebBuilderCapabilityInput(BaseModel):
    """Input parameters for web_builder.build_app capability."""

    prompt: str = Field(
        ...,
        min_length=3,
        max_length=app_config.WEB_BUILDER_MAX_PROMPT_CHARS,
        description="Natural language description of the web application",
    )
    workspace_id: int = Field(..., description="Target workspace ID")
    language: str = Field(
        default="en",
        max_length=10,
        description="Target UI language (en, vi)",
    )
    app_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional application name override",
    )
    user_id: UUID | None = Field(default=None, description="Requesting user ID")


class WebBuilderCapabilityOutput(BaseModel):
    """Output results of web_builder.build_app capability."""

    app_id: str = Field(..., max_length=36)
    workspace_id: int
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=63, pattern=r"^[a-z0-9-]*$")
    status: str = Field(..., max_length=50)
    preview_url: str | None = Field(default=None, max_length=512)
    public_url: str | None = Field(default=None, max_length=512)
    files: list[str] = Field(
        default_factory=list, description="List of generated file paths"
    )
    files_count: int = 0
    message: str | None = Field(default=None, max_length=1000)
    error: str | None = Field(default=None, max_length=1000)
