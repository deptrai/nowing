"""Schemas for social.generate_viral_drafts capability."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.voice_profile import DraftVariation, VoiceProfile


class SocialGenerateDraftsInput(BaseModel):
    topic: str = Field(..., description="Target topic or hook concept to write about.")
    hook_taxonomy: str = Field(
        default="contrarian_hook",
        description="Taxonomy classification of the source post.",
    )
    voice_profile: VoiceProfile | None = Field(
        default=None, description="Learned voice profile."
    )
    target_platform: Literal["twitter", "facebook", "linkedin", "threads"] = Field(
        default="facebook", description="Target platform formatting constraints."
    )
    n_variations: int = Field(
        default=3, description="Number of variations to generate (default 3)."
    )


class SocialGenerateDraftsOutput(BaseModel):
    drafts: list[DraftVariation]
    count: int
