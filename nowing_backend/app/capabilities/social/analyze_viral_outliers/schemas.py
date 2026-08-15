"""Schemas for social.analyze_viral_outliers capability."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.voice_profile import OutlierPostItem


class SocialAnalyzeOutliersInput(BaseModel):
    keywords: list[str] = Field(
        default_factory=list, description="Target niche keywords to search for."
    )
    min_multiplier: float = Field(
        default=3.0, description="Minimum engagement multiplier over author baseline."
    )
    min_engagement: int = Field(
        default=10, description="Minimum engagement score threshold."
    )


class SocialAnalyzeOutliersOutput(BaseModel):
    outliers: list[OutlierPostItem]
    total_found: int
