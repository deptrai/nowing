"""Pydantic schemas for web_builder.build_app capability (Story 27.1, AC-5)."""

from pydantic import BaseModel, Field


class WebBuilderCapabilityInput(BaseModel):
    """Input parameters for web_builder.build_app capability."""

    prompt: str = Field(
        ...,
        min_length=3,
        description="Natural language description of the web application",
    )
    workspace_id: int = Field(..., description="Target workspace ID")
    language: str = Field(default="en", description="Target UI language (en, vi)")
    app_name: str | None = Field(
        default=None, description="Optional application name override"
    )


class WebBuilderCapabilityOutput(BaseModel):
    """Output results of web_builder.build_app capability."""

    app_id: str
    workspace_id: int
    name: str
    slug: str
    status: str
    preview_url: str | None = None
    public_url: str | None = None
    files_count: int = 0
    message: str | None = None
