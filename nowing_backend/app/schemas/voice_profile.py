"""Pydantic schemas for Viral Social Outbound Co-pilot (Story 21.12 / FR-82 / AD-SOC-1 to 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FormattingQuirks(BaseModel):
    emoji_density: Literal["none", "low", "medium", "high"] = "low"
    bullet_style: Literal["numbered_list", "bullet", "none"] = "bullet"
    line_break_frequency: Literal["low", "medium", "high"] = "high"

    model_config = ConfigDict(from_attributes=True)


class VoiceProfile(BaseModel):
    id: int | None = None
    profile_name: str
    tone: str
    average_sentence_length: float = 12.0
    paragraph_cadence: str = "short paragraphs, high whitespace"
    hook_preference: str = "contrarian data hook"
    vocabulary: list[str] = Field(default_factory=list)
    formatting_quirks: FormattingQuirks = Field(default_factory=FormattingQuirks)
    is_active: bool = True
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VoiceAnalysisRequest(BaseModel):
    sample_text: str
    profile_name: str
    platform: str = "facebook"

    @field_validator("sample_text")
    @classmethod
    def validate_min_words(cls, v: str) -> str:
        words = [w for w in v.strip().split() if w]
        if len(words) < 100:
            raise ValueError(
                "Sample text must contain at least 100 words for accurate voice profiling."
            )
        return v


class VoiceProfileResponse(BaseModel):
    profile: VoiceProfile
    message: str = "Voice profile analyzed and saved successfully"


class VoiceProfileListItem(BaseModel):
    id: int
    profile_name: str
    tone: str
    is_active: bool
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VoiceProfileListResponse(BaseModel):
    items: list[VoiceProfileListItem]
    total: int


class DeconstructedElements(BaseModel):
    hook: str
    re_hook: str
    body: str
    cta: str
    taxonomy: Literal["contrarian_hook", "story_shift", "value_list", "data_reveal"] = (
        "contrarian_hook"
    )
    analysis: str = "why_it_worked: captures high attention through disruptive angle and clear value delivery"


class OutlierPostItem(BaseModel):
    id: int | None = None
    platform: str
    external_post_id: str
    author_name: str | None = None
    author_id: str | None = None
    author_url: str | None = None
    post_url: str | None = None
    content: str
    reactions_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    engagement_score: float = 0.0
    baseline_ratio: float = 1.0
    hook_taxonomy: str | None = None
    why_it_worked: str | None = None
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OutlierPostsResponse(BaseModel):
    items: list[OutlierPostItem]
    total: int
    degraded: bool = False


class ManualIngestRequest(BaseModel):
    raw_text: str
    source_url: str | None = None
    platform: str = "facebook"


class ManualIngestResponse(BaseModel):
    platform: str
    source_url: str | None = None
    original_text_redacted: str
    deconstructed_elements: DeconstructedElements


class DraftVariation(BaseModel):
    variation_letter: Literal["A", "B", "C"]
    content: str
    angle: Literal["contrarian", "framework", "case_study"]
    estimated_reading_time_sec: int = 45
    is_thread: bool = False
    thread_tweets: list[str] = Field(default_factory=list)


class GenerateDraftsRequest(BaseModel):
    topic: str
    hook_taxonomy: str = "contrarian_hook"
    voice_profile_id: int | None = None
    voice_profile: VoiceProfile | None = None
    target_platform: Literal["twitter", "facebook", "linkedin", "threads"] = "facebook"
    n_variations: int = 3


class GenerateDraftsResponse(BaseModel):
    drafts: list[DraftVariation]
    token_usage: dict[str, Any] = Field(default_factory=dict)
    billing_event_id: str | None = None
