"""Redis Stream Worker & Celery Processor for Ingested Social Posts (Story 21.8 / AD-SOC-4 / AD-SOC-6).

Reads raw social posts from Redis Stream 'stream:social:raw_posts', extracts contact
numbers, prices, emails, locations, computes intent & fit score, and performs idempotent
UPSERT into PostgreSQL `social_posts` table.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import SocialPost, async_session_maker
from app.proprietary.platforms.xactions.adapter import STREAM_SOCIAL_RAW_POSTS
from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor

logger = logging.getLogger(__name__)

CONSUMER_GROUP_NAME = "social_processors"


def compute_fit_score(raw_entities: dict[str, Any], intent_tag: str, reactions: int = 0, comments: int = 0) -> float:
    """Compute lead quality score (0.0 to 1.0) based on extracted signals."""
    score = 0.0

    # Phone numbers present is a major quality signal
    phones = raw_entities.get("phones", [])
    if phones:
        score += 0.45

    # Intent is commercial (sell/buy/hiring)
    if intent_tag in ("sell", "buy", "hiring"):
        score += 0.25
    elif intent_tag == "seeking":
        score += 0.15

    # Price or email specified
    if raw_entities.get("prices") or raw_entities.get("emails"):
        score += 0.15

    # Location specified
    if raw_entities.get("locations"):
        score += 0.10

    # Social engagement bonus
    if reactions > 10 or comments > 5:
        score += 0.05

    return min(1.0, round(score, 2))


async def process_social_post_event(
    payload: dict[str, Any],
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Extract entities, calculate fit score, and idempotent UPSERT into social_posts."""
    extractor = SocialEntityExtractor()

    platform = payload.get("platform", "facebook")
    external_post_id = str(payload.get("external_post_id", ""))
    content = payload.get("content", "")
    author_id = payload.get("author_id")
    author_name = payload.get("author_name")
    author_url = payload.get("author_url")
    post_url = payload.get("post_url")
    reactions_count = int(payload.get("reactions_count", 0))
    comments_count = int(payload.get("comments_count", 0))
    shares_count = int(payload.get("shares_count", 0))

    media_urls_raw = payload.get("media_urls", "[]")
    if isinstance(media_urls_raw, str):
        try:
            media_urls = json.loads(media_urls_raw)
        except Exception:
            media_urls = []
    else:
        media_urls = media_urls_raw or []

    published_at_raw = payload.get("published_at")
    published_at = None
    if published_at_raw:
        try:
            published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))
        except Exception:
            published_at = datetime.now(UTC)

    # 3-step NLP extraction
    extracted = extractor.extract_all(content)
    intent_tag = extracted["intent"]
    fit_score = compute_fit_score(extracted, intent_tag, reactions_count, comments_count)

    result_data = {
        "platform": platform,
        "external_post_id": external_post_id,
        "author_id": author_id,
        "author_name": author_name,
        "author_url": author_url,
        "post_url": post_url,
        "content": content,
        "intent_tag": intent_tag,
        "fit_score": fit_score,
        "reactions_count": reactions_count,
        "comments_count": comments_count,
        "shares_count": shares_count,
        "media_urls": media_urls,
        "raw_entities": extracted,
        "published_at": published_at,
    }

    if session is not None:
        stmt = pg_insert(SocialPost).values(**result_data)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["platform", "external_post_id"],
            set_={
                "reactions_count": stmt.excluded.reactions_count,
                "comments_count": stmt.excluded.comments_count,
                "shares_count": stmt.excluded.shares_count,
                "raw_entities": stmt.excluded.raw_entities,
                "intent_tag": stmt.excluded.intent_tag,
                "fit_score": stmt.excluded.fit_score,
                "updated_at": datetime.now(UTC),
            },
        )
        await session.execute(upsert_stmt)
        await session.commit()

    return result_data


async def get_async_session():
    """Helper factory for async DB sessions."""
    async with async_session_maker() as session:
        yield session


async def run_social_stream_consumer(
    redis_client: Any | None = None,
    consumer_name: str = "worker-1",
    batch_size: int = 10,
    block_ms: int = 2000,
) -> int:
    """Consume events from Redis stream using Consumer Groups (AD-SOC-4)."""
    created_locally = False
    if redis_client is None:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
        created_locally = True

    try:
        # Ensure consumer group exists
        import contextlib

        with contextlib.suppress(Exception):
            await redis_client.xgroup_create(
                name=STREAM_SOCIAL_RAW_POSTS,
                groupname=CONSUMER_GROUP_NAME,
                id="0",
                mkstream=True,
            )

        try:
            entries = await redis_client.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=consumer_name,
                streams={STREAM_SOCIAL_RAW_POSTS: ">"},
                count=batch_size,
                block=block_ms,
            )
        except Exception as exc:
            logger.error("Error reading from social stream: %s", exc)
            return 0

        if not entries:
            return 0

        processed_count = 0
        async with async_session_maker() as session:
            for _stream_name, messages in entries:
                for msg_id, payload in messages:
                    try:
                        await process_social_post_event(payload, session=session)
                        await redis_client.xack(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME, msg_id)
                        processed_count += 1
                    except Exception as exc:
                        await session.rollback()
                        logger.exception("Failed processing social stream message %s: %s", msg_id, exc)

        return processed_count
    finally:
        if created_locally:
            await redis_client.aclose()
