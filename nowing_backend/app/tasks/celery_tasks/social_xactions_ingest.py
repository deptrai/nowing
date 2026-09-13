"""Celery scheduler & per-target ingest for XActions social targets (Story 21.8).

The meta-scheduler ``check_social_monitored_targets`` runs every minute and
spawns ``ingest_social_target`` for each active ``SocialMonitoredTarget`` whose
``scrape_interval_minutes`` has elapsed since ``last_scraped_at``.

The per-target task uses ``XActionsSocialAdapterV2`` (streamable-http MCP) to
fetch posts and pushes each one to Redis Stream ``stream:social:raw_posts`` with
the target's ``workspace_id`` and internal ``target_id`` attached. Downstream
``social_stream_worker`` picks up the stream, extracts entities, and UPSERTs
into ``social_posts``.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy import or_, select

from app.celery_app import CONNECTORS_QUEUE, celery_app
from app.config import config
from app.db import SocialMonitoredTarget, XActionsProxyBinding
from app.proprietary.platforms.xactions.adapter_v2 import XActionsSocialAdapterV2
from app.proprietary.platforms.xactions.mcp_client import XActionsMcpError
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

SOCIAL_TARGET_LOCK_KEY = "xactions:social_target_lock:{target_id}"
# Per-target task hard time limit is 900s; the Redis lock must outlive the task
# to prevent the scheduler from spawning a duplicate ingest for the same target.
SOCIAL_TARGET_LOCK_MIN_TTL_SECONDS = 960
DEFAULT_FETCH_LIMIT = 20


SUPPORTED_PLATFORMS = {
    "facebook_group",
    "facebook_page",
    "twitter_keyword",
    "twitter_user",
    "tiktok_hashtag",
    "chotot_category",
    "shopee_keyword",
    "topcv_search",
    "vietnamworks_search",
    "linkedin_company",
    "batdongsan_category",
    "masothue_lookup",
    "b2b_registry_search",
}


def _target_lock_key(target_id: int) -> str:
    """Redis key used to serialize ingest for a single social target."""
    return SOCIAL_TARGET_LOCK_KEY.format(target_id=target_id)


def _lock_ttl_for_target(target: SocialMonitoredTarget) -> int:
    """Lock TTL in seconds; at least the configured minimum."""
    interval_seconds = (target.scrape_interval_minutes or 15) * 60
    return max(interval_seconds, SOCIAL_TARGET_LOCK_MIN_TTL_SECONDS)


async def _acquire_target_lock(
    redis_client: aioredis.Redis,
    target_id: int,
    ttl: int,
) -> bool:
    """Try to acquire a Redis lock for the given target."""
    return bool(await redis_client.set(_target_lock_key(target_id), "1", nx=True, ex=ttl))


async def _release_target_lock(
    redis_client: aioredis.Redis,
    target_id: int,
) -> None:
    """Release the target lock, ignoring errors."""
    with contextlib.suppress(Exception):
        await redis_client.delete(_target_lock_key(target_id))


async def _pause_target(
    session,
    target: SocialMonitoredTarget,
    reason: str,
    retry_after_seconds: int | None = None,  # pragma: no mutate
) -> None:
    """Pause a target after a transient scraping failure."""
    target.status = "paused"
    if retry_after_seconds:
        target.last_scraped_at = datetime.now(UTC) + timedelta(
            seconds=retry_after_seconds
        )
    await session.commit()
    logger.warning("Paused social target %s: %s", target.id, reason)


async def _halt_target(
    session,
    target: SocialMonitoredTarget,
    reason: str,
) -> None:
    """Permanently halt a target after a fatal failure."""
    target.status = "error"
    target.is_active = False
    await session.commit()
    logger.error("Halted social target %s: %s", target.id, reason)


@celery_app.task(
    name="ingest_social_target",
    bind=True,
    queue=CONNECTORS_QUEUE,
    soft_time_limit=300,
    time_limit=900,
)
def ingest_social_target_task(self, target_id: int) -> int:
    """Celery task that fetches and streams posts for a single social target."""
    return run_async_celery_task(lambda: _ingest_social_target(self, target_id))


async def _ingest_social_target(task, target_id: int) -> int:
    """Fetch posts for a target and push them to the raw-posts Redis stream."""
    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        async with get_celery_session_maker()() as session:
            target = await session.get(SocialMonitoredTarget, target_id)
            if not target:
                logger.warning("Social target %s not found", target_id)
                return 0

            if not target.is_active or target.status == "error":
                logger.info(
                    "Skipping inactive social target %s (active=%s status=%s)",
                    target_id,
                    target.is_active,
                    target.status,
                )
                return 0

            # Resolve per-account proxy binding (AC 8): fall back to workspace
            # binding in xactions_proxy_bindings when the target lacks
            # explicit account_id/proxy_url.
            if not target.account_id or not target.proxy_url:
                binding = await session.execute(
                    select(XActionsProxyBinding).where(
                        XActionsProxyBinding.workspace_id == target.workspace_id,
                        XActionsProxyBinding.platform == target.platform,
                        XActionsProxyBinding.is_active.is_(True),
                    ).limit(1)
                )
                row = binding.scalars().first()
                if row:
                    if not target.account_id:
                        target.account_id = row.account_id
                    if not target.proxy_url:
                        target.proxy_url = row.proxy_url

            lock_ttl = _lock_ttl_for_target(target)
            if not await _acquire_target_lock(redis_client, target_id, lock_ttl):
                logger.info("Social target %s is already being ingested", target_id)
                return 0

            try:
                async with XActionsSocialAdapterV2() as adapter:
                    posts: list = []

                    try:
                        posts = await adapter.fetch_posts_for_target(target)
                    except XActionsMcpError as exc:
                        if exc.code == "XACT_4291":
                            retry_after = exc.retry_after or 30
                            logger.info(
                                "Rate limited by XActions for target %s; retry in %ss",
                                target_id,
                                retry_after,
                            )
                            raise task.retry(countdown=retry_after) from exc
                        if exc.code in (
                            "ACCOUNT_HIBERNATION",
                            "PROXY_EXHAUSTED",
                            "XACT_5030",
                        ):
                            await _pause_target(session, target, str(exc), exc.retry_after)
                            return 0
                        if exc.code == "XACT_4010":
                            await _halt_target(session, target, str(exc))
                            return 0
                        if exc.code == "XACT_5000":
                            # Signer crash — retry up to 3 times then DLQ/alert
                            raise task.retry(countdown=60, max_retries=3) from exc
                        raise

                    ingested = 0
                    for post in posts:
                        post.target_id = target.id
                        post.workspace_id = target.workspace_id
                        await adapter.ingest_raw_post_to_stream(
                            post,
                            redis_client=redis_client,
                        )
                        ingested += 1

                    target.last_scraped_at = datetime.now(UTC)
                    await session.commit()

                    logger.info(
                        "Ingested %d posts for social target %s (%s)",
                        ingested,
                        target_id,
                        target.platform,
                    )
                    return ingested

            except Exception:  # ingest failure → rollback and re-raise
                await session.rollback()
                raise
            finally:
                await _release_target_lock(redis_client, target_id)
    finally:
        with contextlib.suppress(Exception):
            await redis_client.aclose()


@celery_app.task(name="check_social_monitored_targets")
def check_social_monitored_targets_task() -> int:
    """Meta-scheduler: find due social targets and spawn per-target ingest tasks."""
    return run_async_celery_task(_check_and_trigger_social_targets)


async def _check_and_trigger_social_targets() -> int:
    """Scan active social targets and enqueue ``ingest_social_target`` for due ones."""
    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        async with get_celery_session_maker()() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(SocialMonitoredTarget).where(
                    SocialMonitoredTarget.is_active.is_(True),
                    or_(
                        SocialMonitoredTarget.status == "active",
                        # Allow paused targets whose cooldown has expired to
                        # resume. `_pause_target` sets last_scraped_at into the
                        # future, so once that time passes the target is due.
                        SocialMonitoredTarget.status == "paused",
                    ),
                )
            )
            targets = result.scalars().all()

            due_targets = [
                target
                for target in targets
                if target.last_scraped_at is None
                or target.last_scraped_at
                <= now - timedelta(minutes=target.scrape_interval_minutes or 15)
            ]

            if not due_targets:
                logger.debug("No social targets due for scraping")
                return 0

            logger.info(
                "Found %d social target(s) due for scraping", len(due_targets)
            )

            triggered = 0
            for target in due_targets:
                try:
                    if target.platform not in SUPPORTED_PLATFORMS:
                        logger.debug(
                            "Skipping unsupported platform %r for target %s",
                            target.platform,
                            target.id,
                        )
                        continue

                    if await redis_client.exists(_target_lock_key(target.id)):
                        logger.debug(
                            "Social target %s is locked, skipping", target.id
                        )
                        continue

                    logger.info(
                        "Triggering social ingest for target %s (%s)",
                        target.id,
                        target.platform,
                    )
                    ingest_social_target_task.delay(target.id)
                    triggered += 1
                except Exception:  # per-target schedule failure; continue scheduling remaining targets
                    logger.exception(
                        "Failed to schedule social ingest for target %s",
                        target.id,
                    )
                    continue

            return triggered
    finally:
        with contextlib.suppress(Exception):
            await redis_client.aclose()
