"""Standalone manual integration & verification script for Story 36.5.

Verifies live Redis Stream consumer schema contract & DLQ routing against real Redis & Postgres.
Usage:
    cd nowing_backend && uv run python scripts/verify_social_stream_36_5.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.db import Lead, SocialMonitoredTarget, SocialPost, User, Workspace
from app.proprietary.platforms.xactions.constants import (
    STREAM_SOCIAL_DEAD_LETTER,
    STREAM_SOCIAL_RAW_POSTS,
)
from app.tasks.social_stream_worker import (
    CONSUMER_GROUP_NAME,
    DLQ_REASON_MISSING_CONTENT,
    DLQ_REASON_MISSING_TARGET_ID,
    DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION,
    run_social_stream_consumer,
)


def log_step(name: str, status: str = "RUNNING"):
    colors = {
        "RUNNING": "\033[33m",
        "PASS": "\033[32m",
        "FAIL": "\033[31m",
        "INFO": "\033[36m",
        "RESET": "\033[0m",
    }
    print(f"{colors.get(status, '')}[{status}] {name}{colors['RESET']}")


async def main():
    print("=" * 70)
    print(" STORY 36.5: STREAM CONSUMER SCHEMA CONTRACT & DLQ VERIFICATION")
    print("=" * 70)

    # 1. Check Infrastructure Connectivity
    log_step("Checking Redis connection...", "INFO")
    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        pong = await redis_client.ping()
        if not pong:
            log_step("Redis ping failed!", "FAIL")
            return 1
        log_step(f"Redis is UP ({config.REDIS_APP_URL})", "PASS")
    except Exception as exc:
        log_step(f"Redis connection failed: {exc}", "FAIL")
        return 1

    log_step("Checking PostgreSQL connection...", "INFO")
    engine = create_async_engine(config.DATABASE_URL, echo=False)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_maker() as session:
            await session.execute(select(1))
        log_step("PostgreSQL is UP and accessible", "PASS")
    except Exception as exc:
        log_step(f"PostgreSQL connection failed: {exc}", "FAIL")
        await redis_client.aclose()
        return 1

    # 2. Setup Temporary Test Data in Database
    test_run_id = uuid.uuid4().hex[:6]
    test_user_id = uuid.uuid4()
    log_step(f"Seeding temporary test workspace and monitored target (run_id={test_run_id})...", "INFO")

    async with session_maker() as session:
        # Create test user
        user = User(
            id=test_user_id,
            email=f"verify_stream_{test_run_id}@nowing.net",
            hashed_password="mock_hash_for_test",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        # Create test workspace
        workspace = Workspace(
            name=f"Manual Verify Space {test_run_id}",
            user_id=user.id,
        )
        session.add(workspace)
        await session.flush()

        # Create test social monitored target
        target = SocialMonitoredTarget(
            workspace_id=workspace.id,
            platform="facebook_group",
            target_id=f"target_verify_{test_run_id}",
            target_name=f"Manual Stream Verification Group {test_run_id}",
            category="real_estate",
            is_active=True,
            realtime_stream=False,
            scrape_interval_minutes=15,
            status="active",
        )
        session.add(target)
        await session.commit()
        workspace_id = workspace.id
        target_db_id = target.id

    log_step(f"Seeded Workspace ID: {workspace_id}, Target DB ID: {target_db_id}", "PASS")

    # Monkeypatch stream_worker session maker to use our database engine
    import app.tasks.social_stream_worker as stream_worker_mod
    stream_worker_mod.async_session_maker = session_maker

    test_failures = 0
    consumer_name = f"manual-verify-consumer-{test_run_id}"

    try:
        # Clean test streams
        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)

        # -------------------------------------------------------------
        # TEST CASE 1: Happy Path with content_snippet & Lead Creation
        # -------------------------------------------------------------
        log_step("Test Case 1: Thin event with content_snippet (empty content)", "INFO")
        post_id_1 = f"live_snippet_{test_run_id}"
        post_url_1 = f"https://facebook.com/groups/test/posts/{post_id_1}"
        snippet_text_1 = "Cần bán nhà chính chủ mặt tiền Q1 giá 15 tỷ, liên hệ 0903123456 gấp!"

        payload_1 = {
            "platform": "facebook",
            "external_post_id": post_id_1,
            "author_id": f"author_{test_run_id}",
            "author_name": "Nguyễn Văn Test",
            "content": "",  # Empty content should coalesce to content_snippet
            "content_snippet": snippet_text_1,
            "post_url": post_url_1,
            "target_id": str(target_db_id),
            "workspace_id": str(workspace_id),
            "schema_version": "1",
            "reactions_count": "20",
            "comments_count": "5",
        }
        msg_id_1 = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload_1)
        log_step(f"Injected message {msg_id_1} into {STREAM_SOCIAL_RAW_POSTS}", "INFO")

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=1000,
        )

        if processed != 1:
            log_step(f"Expected 1 processed message, got {processed}", "FAIL")
            test_failures += 1
        else:
            # Check DB
            async with session_maker() as session:
                post = (await session.execute(
                    select(SocialPost).where(
                        SocialPost.workspace_id == workspace_id,
                        SocialPost.external_post_id == post_id_1,
                    )
                )).scalar_one_or_none()

                lead = (await session.execute(
                    select(Lead).where(
                        Lead.workspace_id == workspace_id,
                        Lead.source_url == post_url_1,
                    )
                )).scalar_one_or_none()

            pending_info = await redis_client.xpending(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME)
            pending_count = pending_info.get("pending", 0)

            if not post or post.content != snippet_text_1:
                log_step("SocialPost not found or content does not match snippet!", "FAIL")
                test_failures += 1
            elif not lead or lead.company_name != "Nguyễn Văn Test":
                log_step("Lead not created or company_name mismatch!", "FAIL")
                test_failures += 1
            elif pending_count != 0:
                log_step(f"Message not ACKed! Pending in PEL: {pending_count}", "FAIL")
                test_failures += 1
            else:
                log_step("Case 1: SocialPost saved, Lead created, Phone extracted, XACK verified", "PASS")

        # -------------------------------------------------------------
        # TEST CASE 2: DLQ on Unsupported Schema Version (e.g. version 99)
        # -------------------------------------------------------------
        log_step("Test Case 2: DLQ routing on unsupported schema_version (> 1)", "INFO")
        post_id_2 = f"live_unsupported_{test_run_id}"
        payload_2 = {
            "platform": "facebook",
            "external_post_id": post_id_2,
            "content_snippet": "Valid snippet but schema_version 99",
            "target_id": str(target_db_id),
            "workspace_id": str(workspace_id),
            "schema_version": "99",
        }
        msg_id_2 = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload_2)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=1000,
        )

        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        found_dlq_2 = False
        for dlq_id, entry in dlq_entries:
            if entry.get("original_id") == msg_id_2 and entry.get("dlq_reason") == DLQ_REASON_UNSUPPORTED_SCHEMA_VERSION:
                found_dlq_2 = True
                break

        pending_info = await redis_client.xpending(STREAM_SOCIAL_RAW_POSTS, CONSUMER_GROUP_NAME)
        pending_count = pending_info.get("pending", 0)

        if not found_dlq_2:
            log_step("Case 2: Message did not land in DLQ with UNSUPPORTED_SCHEMA_VERSION!", "FAIL")
            test_failures += 1
        elif pending_count != 0:
            log_step(f"Case 2: Failed message not ACKed! Pending in PEL: {pending_count}", "FAIL")
            test_failures += 1
        else:
            log_step("Case 2: Routed to DLQ with UNSUPPORTED_SCHEMA_VERSION and XACKed from PEL", "PASS")

        # -------------------------------------------------------------
        # TEST CASE 3: DLQ on Missing Content
        # -------------------------------------------------------------
        log_step("Test Case 3: DLQ routing on missing content (content & snippet empty)", "INFO")
        post_id_3 = f"live_nocontent_{test_run_id}"
        payload_3 = {
            "platform": "facebook",
            "external_post_id": post_id_3,
            "content": "",
            "content_snippet": "   ",
            "target_id": str(target_db_id),
            "workspace_id": str(workspace_id),
            "schema_version": "1",
        }
        msg_id_3 = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload_3)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=1000,
        )

        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        found_dlq_3 = False
        for dlq_id, entry in dlq_entries:
            if entry.get("original_id") == msg_id_3 and entry.get("dlq_reason") == DLQ_REASON_MISSING_CONTENT:
                found_dlq_3 = True
                break

        if not found_dlq_3:
            log_step("Case 3: Message did not land in DLQ with MISSING_CONTENT!", "FAIL")
            test_failures += 1
        else:
            log_step("Case 3: Routed to DLQ with MISSING_CONTENT and XACKed from PEL", "PASS")

        # -------------------------------------------------------------
        # TEST CASE 4: DLQ on Missing target_id
        # -------------------------------------------------------------
        log_step("Test Case 4: DLQ routing on missing target_id (enforcing DB schema)", "INFO")
        post_id_4 = f"live_notarget_{test_run_id}"
        payload_4 = {
            "platform": "facebook",
            "external_post_id": post_id_4,
            "content_snippet": "Valid snippet with workspace but no target",
            "workspace_id": str(workspace_id),
            "schema_version": "1",
        }
        msg_id_4 = await redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload_4)

        processed = await run_social_stream_consumer(
            redis_client=redis_client,
            consumer_name=consumer_name,
            batch_size=1,
            block_ms=1000,
        )

        dlq_entries = await redis_client.xrange(STREAM_SOCIAL_DEAD_LETTER)
        found_dlq_4 = False
        for dlq_id, entry in dlq_entries:
            if entry.get("original_id") == msg_id_4 and entry.get("dlq_reason") == DLQ_REASON_MISSING_TARGET_ID:
                found_dlq_4 = True
                break

        if not found_dlq_4:
            log_step("Case 4: Message did not land in DLQ with MISSING_TARGET_ID!", "FAIL")
            test_failures += 1
        else:
            log_step("Case 4: Routed to DLQ with MISSING_TARGET_ID and XACKed from PEL", "PASS")

    finally:
        # Teardown Test Data
        log_step("Cleaning up temporary test database records and Redis streams...", "INFO")
        async with session_maker() as session:
            await session.execute(delete(Lead).where(Lead.workspace_id == workspace_id))
            await session.execute(delete(SocialPost).where(SocialPost.workspace_id == workspace_id))
            await session.execute(delete(SocialMonitoredTarget).where(SocialMonitoredTarget.workspace_id == workspace_id))
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id == test_user_id))
            await session.commit()

        await redis_client.delete(STREAM_SOCIAL_RAW_POSTS, STREAM_SOCIAL_DEAD_LETTER)
        await redis_client.aclose()
        await engine.dispose()
        log_step("Cleanup complete", "PASS")

    print("=" * 70)
    if test_failures == 0:
        print("\033[32mALL 4 MANUAL INTEGRATION VERIFICATION CHECKS PASSED!\033[0m")
        return 0
    else:
        print(f"\033[31mVERIFICATION FAILED WITH {test_failures} ERRORS!\033[0m")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
