"""Executor for social lead search capability (Story 21.8 / AC 5)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy import and_, desc, or_, select

from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.db import SocialPost

from .schemas import SocialPostItem, SocialSearchLeadsInput, SocialSearchLeadsOutput

logger = logging.getLogger(__name__)

RATE_MICROS_PER_ITEM = 2000

GENERIC_DEGRADATION = (
    "Social search is temporarily unavailable. Please try again later."
)


def _escape_like_pattern(value: str) -> str:
    """Escape LIKE/ILIKE wildcards so a keyword cannot alter query semantics."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def build_search_leads_executor() -> Callable[..., Awaitable[SocialSearchLeadsOutput]]:
    """Build the async executor for searching social leads."""

    async def execute(
        payload: SocialSearchLeadsInput,
        ctx: CapabilityContext | None = None,
    ) -> SocialSearchLeadsOutput:
        emit_progress(
            "starting",
            f"Searching social leads for keyword='{payload.keyword}', intent='{payload.intent}'",
            total=payload.limit,
            unit="lead",
        )

        items: list[SocialPostItem] = []
        try:
            if ctx is None or ctx.workspace_id is None:
                raise ValueError("workspace_id is required for social.search_leads")

            workspace_id = ctx.workspace_id
            session = ctx.session
            query = select(SocialPost)

            filters = [
                or_(
                    SocialPost.workspace_id == workspace_id,
                    SocialPost.target.has(workspace_id=workspace_id),
                )
            ]
            if payload.platform:
                filters.append(SocialPost.platform == payload.platform)
            if payload.intent:
                filters.append(SocialPost.intent_tag == payload.intent)
            if payload.min_fit_score > 0.0:
                filters.append(SocialPost.fit_score >= payload.min_fit_score)
            if payload.keyword:
                kw = _escape_like_pattern(payload.keyword)
                filters.append(
                    or_(
                        SocialPost.content.ilike(kw),
                        SocialPost.author_name.ilike(kw),
                    )
                )

            query = query.where(and_(*filters))

            query = (
                query.order_by(
                    desc(SocialPost.published_at), desc(SocialPost.fit_score)
                )
                .offset(payload.offset)
                .limit(payload.limit)
            )
            result = await session.execute(query)
            rows = result.scalars().all()

            for row in rows:
                raw_ent = row.raw_entities if isinstance(row.raw_entities, dict) else {}
                published_at = (
                    row.published_at.isoformat()
                    if isinstance(row.published_at, datetime)
                    else None
                )
                items.append(
                    SocialPostItem(
                        platform=row.platform,
                        external_post_id=row.external_post_id,
                        author_name=row.author_name,
                        author_url=row.author_url,
                        post_url=row.post_url,
                        content=row.content,
                        intent_tag=row.intent_tag,
                        fit_score=row.fit_score,
                        phones=raw_ent.get("phones", []),
                        emails=raw_ent.get("emails", []),
                        prices=raw_ent.get("prices", []),
                        locations=raw_ent.get("locations", []),
                        reactions_count=row.reactions_count,
                        comments_count=row.comments_count,
                        shares_count=row.shares_count,
                        published_at=published_at,
                    )
                )
        except Exception as exc:
            logger.exception("Error executing social.search_leads: %s", exc)
            return SocialSearchLeadsOutput(
                items=[],
                total=0,
                cost_micros=0,
                degraded=True,
                degradation_reason=GENERIC_DEGRADATION,
            )

        emit_progress(
            "done",
            f"Found {len(items)} social lead(s)",
            current=len(items),
            total=payload.limit,
            unit="lead",
        )

        cost = len(items) * RATE_MICROS_PER_ITEM

        return SocialSearchLeadsOutput(
            items=items,
            total=len(items),
            cost_micros=cost,
            degraded=False,
        )

    return execute
