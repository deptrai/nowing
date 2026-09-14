"""Celery scheduler & per-target ingest for XActions social targets (Story 21.8).

The meta-scheduler ``check_social_monitored_targets`` runs every minute and
spawns ``ingest_social_target`` for each active ``SocialMonitoredTarget`` whose
``scrape_interval_minutes`` has elapsed since ``last_scraped_at``.

The per-target task uses ``XActionsSocialAdapterV2`` (streamable-http MCP) to
fetch posts and, in legacy dual-write mode, pushes each one to Redis Stream
``stream:social:raw_posts`` with the target's ``workspace_id`` and internal
``target_id`` attached. When ``XACTIONS_STREAM_SINGLE_WRITER_ENABLED`` is active,
stream publishing is bypassed (XActions sole-writer architecture AD-4). Downstream
``social_stream_worker`` picks up the stream, extracts entities, and UPSERTs
into ``social_posts``.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import or_, select

from app.celery_app import CONNECTORS_QUEUE, celery_app
from app.config import config
from app.db import SocialMonitoredTarget, XActionsProxyBinding
from app.proprietary.platforms.xactions.adapter_v2 import (
    TargetUnsupportedError,
    XActionsSocialAdapterV2,
)
from app.proprietary.platforms.xactions.constants import STREAM_SOCIAL_DEAD_LETTER
from app.proprietary.platforms.xactions.error_map import (
    BehaviorDecision,
    TaskBehavior,
    clamp_cooldown,
    resolve_task_behavior,
)
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
    suggested_action: str | None = None,
) -> None:
    """Pause a target after a transient scraping failure."""
    target.status = "paused"
    # decision.cooldown_seconds is already clamped in error_map; clamp again
    # defensively for direct callers passing raw retry_after values.
    cooldown = clamp_cooldown(retry_after_seconds)
    target.last_scraped_at = datetime.now(UTC) + timedelta(seconds=cooldown)
    await session.commit()
    if suggested_action:
        logger.warning(
            "Paused social target %s: %s (suggested: %s)",
            target.id,
            reason,
            suggested_action,
        )
    else:
        logger.warning("Paused social target %s: %s", target.id, reason)


def _get_task_retries(task: Any) -> int:
    """Safely extract integer retry count from Celery task request or test mock."""
    req = getattr(task, "request", None)
    if req is None:
        return 0
    raw = getattr(req, "retries", 0)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return max(0, raw)
    try:
        return max(0, int(float(str(raw))))
    except (TypeError, ValueError):
        return 0


async def _write_dlq(
    redis_client: aioredis.Redis,
    target: SocialMonitoredTarget,
    exc: Exception,
    decision: BehaviorDecision,
    retries: int,
) -> None:
    """Write exhausted retry event to the dead-letter stream."""
    try:
        normalized_code = decision.code
        await redis_client.xadd(
            STREAM_SOCIAL_DEAD_LETTER,
            {
                "original_id": str(target.id),
                "payload": json.dumps(
                    {
                        "target_id": target.id,
                        "platform": target.platform,
                        "workspace_id": target.workspace_id,
                        "account_id": target.account_id,
                        "code": normalized_code if normalized_code else None,
                        "suggested_action": decision.suggested_action,
                        "retries": retries,
                    },
                    default=str,
                ),
                "error": str(exc),
                "code": normalized_code,
                "suggested_action": str(decision.suggested_action or ""),
                "retries": str(retries),
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )
    except Exception:
        logger.exception(
            "Failed to move social target %s to dead-letter queue",
            target.id,
        )


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


async def _mark_target_unsupported(
    session,
    target: SocialMonitoredTarget,
    reason: str,
) -> None:
    """Permanently mark a target as unsupported after a fatal unsupported failure."""
    target.status = "unsupported"
    target.is_active = False
    await session.commit()
    logger.warning(
        "Marked social target %s (%s) as unsupported: %s",
        target.id,
        target.platform,
        reason,
    )


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

            if not target.is_active or target.status in ("error", "unsupported"):
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
                    except TargetUnsupportedError as exc:
                        await _mark_target_unsupported(session, target, str(exc))
                        return 0
                    except XActionsMcpError as exc:
                        decision = resolve_task_behavior(exc)
                        if decision.behavior is TaskBehavior.RETRY:
                            retries = _get_task_retries(task)
                            retries_exhausted = (
                                decision.max_retries is not None
                                and retries >= decision.max_retries
                            )
                            if retries_exhausted:
                                if (
                                    decision.exhausted_behavior
                                    is TaskBehavior.HALT
                                ):
                                    if decision.write_dlq:
                                        await _write_dlq(
                                            redis_client,
                                            target,
                                            exc,
                                            decision,
                                            retries,
                                        )
                                    await _halt_target(
                                        session, target, decision.reason
                                    )
                                    return 0
                                if (
                                    decision.exhausted_behavior
                                    is TaskBehavior.PAUSE
                                ):
                                    await _pause_target(
                                        session,
                                        target,
                                        decision.reason,
                                        retry_after_seconds=decision.cooldown_seconds,
                                    )
                                    return 0
                                if (
                                    decision.exhausted_behavior
                                    is TaskBehavior.RAISE
                                ):
                                    raise exc
                                # No exhausted_behavior -> surface the original
                                # error rather than triggering MaxRetriesExceededError.
                                raise exc
                            await session.commit()
                            logger.info(
                                "Retrying social target %s in %ss (attempt %d/%s): %s",
                                target_id,
                                decision.countdown,
                                retries + 1,
                                decision.max_retries
                                if decision.max_retries is not None
                                else "inf",
                                decision.reason,
                            )
                            raise task.retry(
                                exc=exc,
                                countdown=decision.countdown,
                                max_retries=decision.max_retries,
                            ) from exc
                        if decision.behavior is TaskBehavior.PAUSE:
                            await _pause_target(
                                session,
                                target,
                                decision.reason,
                                retry_after_seconds=decision.cooldown_seconds,
                                suggested_action=decision.suggested_action,
                            )
                            return 0
                        if decision.behavior is TaskBehavior.HALT:
                            await _halt_target(session, target, decision.reason)
                            return 0
                        raise exc

                    ingested = 0
                    if not config.XACTIONS_STREAM_SINGLE_WRITER_ENABLED:
                        for post in posts:
                            post.target_id = target.id
                            post.workspace_id = target.workspace_id
                            await adapter.ingest_raw_post_to_stream(
                                post,
                                redis_client=redis_client,
                            )
                            ingested += 1
                    else:
                        ingested = len(posts)
                        logger.info(
                            "Single-writer mode enabled; bypassed raw-posts stream publish for social target %s (%d posts)",
                            target_id,
                            ingested,
                        )

                    target.last_scraped_at = datetime.now(UTC)
                    if target.status == "paused":
                        # Successful resume — paused was a transient cooldown,
                        # not a persistent state. Restore to active so the
                        # status column reflects the real lifecycle.
                        target.status = "active"
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

            # Due semantics differ per status:
            # - "active": periodic scrape — due once scrape_interval has elapsed
            #   since last_scraped_at.
            # - "paused": transient cooldown — _pause_target pushed
            #   last_scraped_at into the future; due as soon as that timestamp
            #   passes (do NOT also subtract scrape_interval, otherwise the
            #   effective pause becomes cooldown + interval, doubling the wait).
            due_targets = []
            for target in targets:
                if target.last_scraped_at is None:
                    due_targets.append(target)
                    continue
                if target.status == "paused":
                    if target.last_scraped_at <= now:
                        due_targets.append(target)
                else:  # "active" (and any other non-error status)
                    interval = timedelta(minutes=target.scrape_interval_minutes or 15)
                    if target.last_scraped_at <= now - interval:
                        due_targets.append(target)

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
