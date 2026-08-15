"""Outlier Detection & Statistical Baseline Engine (Story 21.12 / AC 2)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import SocialPost
from app.schemas.voice_profile import OutlierPostItem

logger = logging.getLogger(__name__)


def _get_redis() -> Any | None:
    try:
        from redis import asyncio as aioredis

        return aioredis.from_url(
            config.REDIS_APP_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    except Exception:
        return None


def calculate_engagement_score(reactions: int, comments: int, shares: int) -> int:
    """AC 2: Score = Reactions + 2*Comments + 3*Shares."""
    return int(reactions + (2 * comments) + (3 * shares))


def evaluate_outlier_ratio(
    engagement_score: int,
    author_baseline: float,
    min_multiplier: float = 3.0,
    min_engagement: int = 10,
) -> tuple[bool, float]:
    """Zero-division guard: Baseline = max(author_baseline, 1.0).

    Condition: (Score >= min_engagement) and (Ratio >= min_multiplier).
    """
    safe_baseline = max(float(author_baseline), 1.0)
    ratio = round(float(engagement_score) / safe_baseline, 2)
    is_outlier = (engagement_score >= min_engagement) and (ratio >= min_multiplier)
    return is_outlier, ratio


class OutlierDetector:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def get_author_baseline(
        self,
        workspace_id: int,
        platform: str,
        author_id: str,
        client_id: str = "default",
    ) -> float:
        """Get or compute author baseline engagement score with Redis caching (AD-SOC-1 / AD-31)."""
        cache_key = f"cache:social:baseline:{workspace_id}:{platform}:{author_id}"
        redis = _get_redis()
        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    return float(cached)
            except Exception as e:
                logger.debug(f"Redis get error: {e}")

        # Compute average from DB
        avg_score: float = 10.0
        if self.session:
            stmt = select(
                func.avg(
                    func.coalesce(SocialPost.reactions_count, 0)
                    + (2 * func.coalesce(SocialPost.comments_count, 0))
                    + (3 * func.coalesce(SocialPost.shares_count, 0))
                )
            ).where(
                SocialPost.workspace_id == workspace_id,
                SocialPost.platform == platform,
                SocialPost.author_id == author_id,
            )
            result = await self.session.execute(stmt)
            val = result.scalar_one_or_none()
            if val is not None:
                avg_score = float(val)

        # Cache baseline for 3600s (1 hour)
        if redis:
            try:
                await redis.setex(cache_key, 3600, str(avg_score))
            except Exception as e:
                logger.debug(f"Redis setex error: {e}")

        return avg_score

    async def find_outliers(
        self,
        workspace_id: int,
        client_id: str = "default",
        target_keywords: list[str] | None = None,
        min_multiplier: float = 3.0,
        min_engagement: int = 10,
    ) -> list[OutlierPostItem]:
        """Find outlier posts (>= 3x author baseline) for target keywords/platform."""
        if not self.session:
            return []

        stmt = select(SocialPost).where(
            SocialPost.workspace_id == workspace_id,
        )

        if target_keywords:
            for kw in target_keywords:
                safe_kw = kw.replace("%", "\\%").replace("_", "\\_")
                stmt = stmt.where(SocialPost.content.ilike(f"%{safe_kw}%"))

        stmt = stmt.order_by(SocialPost.published_at.desc()).limit(100)
        result = await self.session.execute(stmt)
        posts = result.scalars().all()

        outliers: list[OutlierPostItem] = []
        for p in posts:
            author_ref = p.author_id or p.author_name or "unknown"
            baseline = await self.get_author_baseline(
                workspace_id=workspace_id,
                platform=p.platform,
                author_id=author_ref,
                client_id=client_id,
            )
            score = calculate_engagement_score(
                reactions=p.reactions_count or 0,
                comments=p.comments_count or 0,
                shares=p.shares_count or 0,
            )
            is_outlier, ratio = evaluate_outlier_ratio(
                engagement_score=score,
                author_baseline=baseline,
                min_multiplier=min_multiplier,
                min_engagement=min_engagement,
            )
            if is_outlier:
                outliers.append(
                    OutlierPostItem(
                        id=p.id,
                        platform=p.platform,
                        external_post_id=p.external_post_id,
                        author_name=p.author_name,
                        author_id=p.author_id,
                        author_url=p.author_url,
                        post_url=p.post_url,
                        content=p.content,
                        reactions_count=p.reactions_count or 0,
                        comments_count=p.comments_count or 0,
                        shares_count=p.shares_count or 0,
                        engagement_score=score,
                        baseline_ratio=ratio,
                        published_at=p.published_at.isoformat()
                        if p.published_at
                        else None,
                    )
                )

        return outliers
