"""``social.search_leads`` capability package."""

from typing import Any

from .definition import SOCIAL_SEARCH_LEADS
from .executor import build_search_leads_executor
from .schemas import SocialPostItem, SocialSearchLeadsInput, SocialSearchLeadsOutput

__all__ = [
    "SOCIAL_SEARCH_LEADS",
    "SocialPostItem",
    "SocialSearchLeadsInput",
    "SocialSearchLeadsOutput",
    "social_search_posts",
]


async def social_search_posts(
    platform: str | None = None,
    intent: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    min_fit_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Helper function to search social posts directly (Story 21.8 / AC 5)."""
    executor = build_search_leads_executor()
    payload = SocialSearchLeadsInput(
        platform=platform,
        intent=intent,
        keyword=keyword,
        limit=limit,
        min_fit_score=min_fit_score,
    )
    result: SocialSearchLeadsOutput = await executor(payload)
    return [item.model_dump() for item in result.items]
