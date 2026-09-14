"""Integration tests for XActions Redis Stream social posts buffer & processor (Story 36.5).

Requires PostgreSQL and Redis. Skipped automatically when either is unavailable.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.tasks.social_stream_worker as stream_worker
from app.config import config
from app.db import Lead, SocialMonitoredTarget, SocialPost
from app.proprietary.platforms.xactions.constants import (
    STREAM_SOCIAL_DEAD_LETTER,
    STREAM_SOCIAL_RAW_POSTS,
)
from app.tasks.celery_tasks.social_stream_worker import run_social_stream_consumer
from app.tasks.social_stream_worker import (
    CONSUMER_GROUP_NAME,
    DLQ_REASON_MISSING_CONTENT,
    DLQ_REASON_MISSING_TARGET_ID,
    DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION,
)

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
        target_id=f"bds_stream_group_{uuid.uuid4().hex[:6]}",
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
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        payload = {
            "platform": "facebook",
            "external_post_id": f"fb_stream_{uuid.uuid4().hex[:6]}",
            "author_id": "usr_999",
            "author_name": "Trần Thị B",
            "content": "Bán gấp nhà mặt tiền Quận 1 giá 25 tỷ, liên hệ o909123456 chính chủ.",
            "post_url": f"https://facebook.com/groups/bds/posts/{uuid.uuid4().hex[:6]}",
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
                    SocialPost.external_post_id == payload["external_post_id"],
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

        # Verify message acknowledged from stream (no pending entries)
        pending_info = await redis_client.xpending(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME)
        assert pending_info["pending"] == 0
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_social_redis_stream_content_snippet_alias_processing(
    platform_db_session: AsyncSession,
    platform_db_workspace,
    db_social_target,
    monkeypatch,
):
    """Thin event with content_snippet (and empty content) is ingested, parsed, and persisted."""
    @asynccontextmanager
    async def _test_session_maker():
        yield platform_db_session

    monkeypatch.setattr(stream_worker, "async_session_maker", _test_session_maker)

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        consumer_name = f"test-consumer-{uuid.uuid4().hex[:8]}"
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        post_id = f"snippet_post_{uuid.uuid4().hex[:6]}"
        post_url = f"https://facebook.com/groups/bds/posts/{post_id}"
        snippet_text = "Cần bán gấp shophouse Vinhomes Grand Park, SĐT 0918123456, giá 8 tỷ."

        # Emit thin event matching XActions REQ-X2 contract
        payload = {
            "platform": "facebook",
            "external_post_id": post_id,
            "author_id": "usr_xactions",
            "author_name": "Lê Văn C",
            "content": "",  # Empty content should be coalesced to content_snippet
            "content_snippet": snippet_text,
            "post_url": post_url,
            "target_id": str(db_social_target.id),
            "workspace_id": str(platform_db_workspace.id),
            "schema_version": "1",
        }

        msg_id = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload)
        assert msg_id is not None

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=2000,
        )

        assert processed == 1

        # Assert post is saved with content from content_snippet
        post = (
            await platform_db_session.execute(
                select(SocialPost).where(
                    SocialPost.platform == "facebook",
                    SocialPost.external_post_id == post_id,
                )
            )
        ).scalar_one()

        assert post.content == snippet_text
        assert "0918123456" in post.raw_entities["phones"]
        assert post.intent_tag == "sell"
        assert post.workspace_id == platform_db_workspace.id
        assert post.target_id == db_social_target.id

        # Assert Lead was created
        lead = (
            await platform_db_session.execute(
                select(Lead).where(
                    Lead.workspace_id == platform_db_workspace.id,
                    Lead.source == "social",
                    Lead.source_url == post_url,
                )
            )
        ).scalar_one()
        assert lead.company_name == "Lê Văn C"

        # Assert XACK was sent (no pending entries)
        pending_info = await redis_client.xpending(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME)
        assert pending_info["pending"] == 0

        # Assert DLQ is empty
        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        assert len(dlq_entries) == 0
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_social_redis_stream_dlq_on_unsupported_schema_version(
    platform_db_session: AsyncSession,
    platform_db_workspace,
    db_social_target,
    monkeypatch,
):
    """Event with schema_version > 1 routes to stream:social:failed with UNSUPPORTED_SCHEMA_VERSION."""
    @asynccontextmanager
    async def _test_session_maker():
        yield platform_db_session

    monkeypatch.setattr(stream_worker, "async_session_maker", _test_session_maker)

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        consumer_name = f"test-consumer-{uuid.uuid4().hex[:8]}"
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        post_id = f"future_schema_{uuid.uuid4().hex[:6]}"
        payload = {
            "platform": "facebook",
            "external_post_id": post_id,
            "content_snippet": "Future schema version test content",
            "target_id": str(db_social_target.id),
            "workspace_id": str(platform_db_workspace.id),
            "schema_version": "99",  # Unsupported version
        }

        orig_id = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=2000,
        )

        assert processed == 0

        # Verify no post inserted into PostgreSQL
        post = (
            await platform_db_session.execute(
                select(SocialPost).where(SocialPost.external_post_id == post_id)
            )
        ).scalar_one_or_none()
        assert post is None

        # Verify message routed to dead-letter queue
        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        assert len(dlq_entries) == 1
        _dlq_id, dlq_data = dlq_entries[0]
        assert dlq_data["original_id"] == orig_id
        assert dlq_data["dlq_reason"] == DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION

        # Verify message was XACK'd from raw_posts (not left hanging in PEL)
        pending_info = await redis_client.xpending(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME)
        assert pending_info["pending"] == 0
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_social_redis_stream_dlq_on_missing_content(
    platform_db_session: AsyncSession,
    platform_db_workspace,
    db_social_target,
    monkeypatch,
):
    """Event missing both content and content_snippet routes to DLQ with MISSING_CONTENT and XACKs."""
    @asynccontextmanager
    async def _test_session_maker():
        yield platform_db_session

    monkeypatch.setattr(stream_worker, "async_session_maker", _test_session_maker)

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        consumer_name = f"test-consumer-{uuid.uuid4().hex[:8]}"
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        post_id = f"no_content_{uuid.uuid4().hex[:6]}"
        payload = {
            "platform": "facebook",
            "external_post_id": post_id,
            "target_id": str(db_social_target.id),
            "workspace_id": str(platform_db_workspace.id),
            "content": "",
            "content_snippet": "   ",  # Whitespace only
            "schema_version": "1",
        }

        orig_id = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=2000,
        )

        assert processed == 0

        # Verify routed to DLQ with MISSING_CONTENT
        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        assert len(dlq_entries) == 1
        _, dlq_data = dlq_entries[0]
        assert dlq_data["original_id"] == orig_id
        assert dlq_data["dlq_reason"] == DLQ_REASON_MISSING_CONTENT

        # Verify XACK'd (PEL clean)
        pending_info = await redis_client.xpending(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME)
        assert pending_info["pending"] == 0
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_social_redis_stream_dlq_on_missing_target_id(
    platform_db_session: AsyncSession,
    platform_db_workspace,
    monkeypatch,
):
    """Event missing target_id routes to DLQ with MISSING_TARGET_ID (DB NOT NULL constraint enforcement)."""
    @asynccontextmanager
    async def _test_session_maker():
        yield platform_db_session

    monkeypatch.setattr(stream_worker, "async_session_maker", _test_session_maker)

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        consumer_name = f"test-consumer-{uuid.uuid4().hex[:8]}"
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        post_id = f"no_target_{uuid.uuid4().hex[:6]}"
        payload = {
            "platform": "facebook",
            "external_post_id": post_id,
            "content_snippet": "Some valid content snippet text",
            "workspace_id": str(platform_db_workspace.id),
            "schema_version": "1",
            # target_id omitted
        }

        orig_id = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=2000,
        )

        assert processed == 0

        # Verify routed to DLQ with MISSING_TARGET_ID
        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        assert len(dlq_entries) == 1
        _, dlq_data = dlq_entries[0]
        assert dlq_data["original_id"] == orig_id
        assert dlq_data["dlq_reason"] == DLQ_REASON_MISSING_TARGET_ID

        # Verify XACK'd
        pending_info = await redis_client.xpending(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME)
        assert pending_info["pending"] == 0
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()


# ---------------------------------------------------------------------------
# Story 36.5 gap-fill — PEL-drain guarantee and REQ-X2 realistic stream shape.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_social_redis_stream_pel_fully_drained_after_mixed_batch(
    platform_db_session: AsyncSession,
    platform_db_workspace,
    db_social_target,
    monkeypatch,
):
    """G11/G13 [P1]: A mixed batch (valid + MISSING_CONTENT + UNSUPPORTED_SCHEMA_VERSION)
    in a single consumer run leaves the PEL fully drained — every message either
    processed+XACK'd or DLQ+XACK'd. This is the spec's core guarantee: 'message
    không bao giờ nằm lại trong PEL'."""
    @asynccontextmanager
    async def _test_session_maker():
        yield platform_db_session

    monkeypatch.setattr(stream_worker, "async_session_maker", _test_session_maker)

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        consumer_name = f"test-consumer-{uuid.uuid4().hex[:8]}"
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        run_id = uuid.uuid4().hex[:6]

        valid_payload = {
            "platform": "facebook",
            "external_post_id": f"valid_{run_id}",
            "content_snippet": "Bán nhà Q1 giá tốt, chính chủ.",
            "workspace_id": str(platform_db_workspace.id),
            "target_id": str(db_social_target.id),
            "schema_version": "1",
        }
        missing_content_payload = {
            "platform": "facebook",
            "external_post_id": f"nocontent_{run_id}",
            "workspace_id": str(platform_db_workspace.id),
            "target_id": str(db_social_target.id),
            "content": "",
            "content_snippet": "   ",
            "schema_version": "1",
        }
        future_version_payload = {
            "platform": "facebook",
            "external_post_id": f"future_{run_id}",
            "content_snippet": "Future schema content",
            "workspace_id": str(platform_db_workspace.id),
            "target_id": str(db_social_target.id),
            "schema_version": "99",
        }

        for p in (valid_payload, missing_content_payload, future_version_payload):
            await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, p)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=10,
            block_ms=2000,
        )

        # Exactly one valid message processed.
        assert processed == 1

        # The valid post persisted to social_posts.
        post = (
            await platform_db_session.execute(
                select(SocialPost).where(
                    SocialPost.external_post_id == f"valid_{run_id}",
                    SocialPost.workspace_id == platform_db_workspace.id,
                )
            )
        ).scalar_one()
        assert post.content == "Bán nhà Q1 giá tốt, chính chủ."

        # Two schema violations routed to DLQ with correct reasons.
        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        assert len(dlq_entries) == 2
        reasons = {d["dlq_reason"] for _, d in dlq_entries}
        assert reasons == {
            DLQ_REASON_MISSING_CONTENT,
            DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION,
        }

        # Core guarantee: PEL fully drained — no message left pending.
        pending_info = await redis_client.xpending(
            STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME
        )
        assert pending_info["pending"] == 0
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_social_redis_stream_reqx2_thin_event_string_fields(
    platform_db_session: AsyncSession,
    platform_db_workspace,
    db_social_target,
    monkeypatch,
):
    """G12 [P1]: REQ-X2 thin event over real Redis — every field arrives as a
    string (xadd coercion). schema_version="1" and content_snippet-only (no
    `content` key at all) must persist successfully end-to-end."""
    @asynccontextmanager
    async def _test_session_maker():
        yield platform_db_session

    monkeypatch.setattr(stream_worker, "async_session_maker", _test_session_maker)

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        consumer_name = f"test-consumer-{uuid.uuid4().hex[:8]}"
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        run_id = uuid.uuid4().hex[:6]
        snippet_text = f"REQ-X2 thin event body {run_id}"

        # Exact REQ-X2 shape: content_snippet only, no `content` key, all fields
        # coerced to str by xadd (including schema_version and ids).
        payload = {
            "platform": "facebook_group",
            "external_post_id": f"reqx2_{run_id}",
            "content_snippet": snippet_text,
            "workspace_id": str(platform_db_workspace.id),
            "target_id": str(db_social_target.id),
            "schema_version": "1",
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
                    SocialPost.external_post_id == f"reqx2_{run_id}",
                    SocialPost.workspace_id == platform_db_workspace.id,
                )
            )
        ).scalar_one()
        # content_snippet coalesced into content and persisted.
        assert post.content == snippet_text

        # Nothing went to DLQ.
        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        assert len(dlq_entries) == 0

        # PEL drained.
        pending_info = await redis_client.xpending(
            STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME
        )
        assert pending_info["pending"] == 0
    finally:
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()
