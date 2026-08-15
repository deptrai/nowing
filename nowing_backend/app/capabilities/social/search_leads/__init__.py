"""``social.search_leads`` capability package."""

from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.db import async_session_maker

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


async def _run_search(
    payload: SocialSearchLeadsInput,
    ctx: CapabilityContext,
) -> list[dict[str, Any]]:
    """Run the executor with the provided auth/tenant context."""
    executor = build_search_leads_executor()
    result: SocialSearchLeadsOutput = await executor(payload, ctx)
    return [item.model_dump() for item in result.items]


async def social_search_posts(
    platform: str | None = None,
    intent: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    min_fit_score: float = 0.0,
    workspace_id: int | None = None,
    ctx: CapabilityContext | None = None,
) -> list[dict[str, Any]]:
    """Helper function to search social posts directly (Story 21.8 / AC 5).

    Requires either a ``workspace_id`` or an existing ``CapabilityContext``
    carrying the tenant and a database session.
    """
    if ctx is not None:
        payload = SocialSearchLeadsInput(
            platform=platform,
            intent=intent,
            keyword=keyword,
            limit=limit,
            min_fit_score=min_fit_score,
        )
        return await _run_search(payload, ctx)

    if workspace_id is None:
        raise ValueError("workspace_id is required for social_search_posts")

    async with async_session_maker() as session:
        payload = SocialSearchLeadsInput(
            platform=platform,
            intent=intent,
            keyword=keyword,
            limit=limit,
            min_fit_score=min_fit_score,
        )
        return await _run_search(
            payload,
            CapabilityContext(session=session, workspace_id=workspace_id),
        )
