"""Integration tests for XActions Redis Stream social posts buffer & processor.

Requires PostgreSQL and Redis. Skipped automatically when either is unavailable.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.tasks.celery_tasks.social_stream_worker as stream_worker
from app.config import config
from app.db import Lead, SocialMonitoredTarget, SocialPost
from app.proprietary.platforms.xactions.constants import STREAM_SOCIAL_RAW_POSTS
from app.tasks.celery_tasks.social_stream_worker import run_social_stream_consumer

pytestmark = [pytest.mark.integration]


async def _redis_available() -> bool:
    try:
        client = aioredis.from_url(
            config.REDIS_APP_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        pong = await client.ping()
        await client.aclose()
        return bool(pong)
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def _skip_if_no_redis():
    if not await _redis_available():
        pytest.skip("Redis unavailable — skipping social stream integration test")


@pytest.fixture
async def db_social_target(
    platform_db_session: AsyncSession,
    platform_db_workspace,
) -> SocialMonitoredTarget:
    target = SocialMonitoredTarget(
        workspace_id=platform_db_workspace.id,
        platform="facebook_group",
        target_id="bds_stream_group",
        target_name="Stream Test Group",
        category="general",
        is_active=True,
        realtime_stream=False,
        scrape_interval_minutes=15,
        status="active",
    )
    platform_db_session.add(target)
    await platform_db_session.flush()
    return target


@pytest.mark.asyncio
async def test_social_redis_stream_event_processing(
    platform_db_session: AsyncSession,
    platform_db_workspace,
    db_social_target,
    monkeypatch,
):
    """A raw event pushed to stream:social:raw_posts is consumed and persisted."""
    @asynccontextmanager
    async def _test_session_maker():
        yield platform_db_session

    monkeypatch.setattr(stream_worker, "async_session_maker", _test_session_maker)

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        consumer_name = f"test-consumer-{uuid.uuid4().hex[:8]}"
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS)

        payload = {
            "platform": "facebook",
            "external_post_id": "fb_stream_001",
            "author_id": "usr_999",
            "author_name": "Trần Thị B",
            "content": "Bán gấp nhà mặt tiền Quận 1 giá 25 tỷ, liên hệ o909123456 chính chủ.",
            "post_url": "https://facebook.com/groups/bds/posts/001",
            "reactions_count": "50",
            "comments_count": "12",
            "shares_count": "3",
            "target_id": str(db_social_target.id),
            "workspace_id": str(platform_db_workspace.id),
            "published_at": "2026-08-15T09:30:00Z",
            "category": "real_estate",
            "scraper_id": "test-scraper",
            "benchmark_health": "ok",
            "benchmark_alert": "false",
        }

        await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=2000,
        )

        assert processed == 1

        post = (
            await platform_db_session.execute(
                select(SocialPost).where(
                    SocialPost.platform == "facebook",
                    SocialPost.external_post_id == "fb_stream_001",
                )
            )
        ).scalar_one()

        assert post.workspace_id == platform_db_workspace.id
        assert post.target_id == db_social_target.id
        assert post.content == payload["content"]
        assert "0909123456" in post.raw_entities["phones"]
        assert post.intent_tag == "sell"
        assert post.fit_score > 0
        assert post.category == "real_estate"
        assert post.scraper_id == "test-scraper"
        assert post.benchmark_health == "ok"
        assert post.benchmark_alert is False

        lead = (
            await platform_db_session.execute(
                select(Lead).where(
                    Lead.workspace_id == platform_db_workspace.id,
                    Lead.source == "social",
                    Lead.source_url == payload["post_url"],
                )
            )
        ).scalar_one()
        assert lead.company_name == "Trần Thị B"
        assert lead.workspace_id == platform_db_workspace.id
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS)
        await redis_client.aclose()
