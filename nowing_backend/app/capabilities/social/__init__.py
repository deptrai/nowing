"""Social capabilities package (Story 21.8, 21.12)."""

from app.capabilities.social.analyze_viral_outliers import (
    SOCIAL_ANALYZE_VIRAL_OUTLIERS,
    SocialAnalyzeOutliersInput,
    SocialAnalyzeOutliersOutput,
)
from app.capabilities.social.generate_viral_drafts import (
    SOCIAL_GENERATE_VIRAL_DRAFTS,
    SocialGenerateDraftsInput,
    SocialGenerateDraftsOutput,
)
from app.capabilities.social.learn_voice import (
    SOCIAL_LEARN_VOICE,
    SocialLearnVoiceInput,
    SocialLearnVoiceOutput,
)
from app.capabilities.social.search_leads import (
    SOCIAL_SEARCH_LEADS,
    SocialPostItem,
    SocialSearchLeadsInput,
    SocialSearchLeadsOutput,
)

__all__ = [
    "SOCIAL_ANALYZE_VIRAL_OUTLIERS",
    "SOCIAL_GENERATE_VIRAL_DRAFTS",
    "SOCIAL_LEARN_VOICE",
    "SOCIAL_SEARCH_LEADS",
    "SocialAnalyzeOutliersInput",
    "SocialAnalyzeOutliersOutput",
    "SocialGenerateDraftsInput",
    "SocialGenerateDraftsOutput",
    "SocialLearnVoiceInput",
    "SocialLearnVoiceOutput",
    "SocialPostItem",
    "SocialSearchLeadsInput",
    "SocialSearchLeadsOutput",
]
