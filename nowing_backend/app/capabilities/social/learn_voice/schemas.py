"""Schemas for social.learn_voice capability."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.voice_profile import VoiceProfile


class SocialLearnVoiceInput(BaseModel):
    sample_text: str = Field(
        ..., description="Writing sample text (at least 100 words)."
    )
    profile_name: str = Field(
        ..., description="Name for the learned persona/voice profile."
    )
    platform: Literal["facebook", "twitter", "linkedin", "tiktok", "general"] = Field(
        default="facebook", description="Platform style context."
    )

    @field_validator("sample_text")
    @classmethod
    def validate_min_words(cls, v: str) -> str:
        words = [w for w in v.strip().split() if w]
        if len(words) < 100:
            raise ValueError("Sample text must contain at least 100 words.")
        return v


class SocialLearnVoiceOutput(BaseModel):
    profile: VoiceProfile
    message: str = "Voice profile analyzed successfully."
