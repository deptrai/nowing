"""Celery task to detect and mark stale meeting-minutes rows as failed.

A row is considered stale when it is still PENDING or PROCESSING but its
Redis heartbeat key has expired.  Active workers set a short-lived heartbeat;
if the worker crashes the key expires and this task marks the row FAILED so
the UI does not show a perpetual "processing" card.
"""

from __future__ import annotations

import logging

import redis
from sqlalchemy import update
from sqlalchemy.future import select

from app.celery_app import celery_app
from app.config import config
from app.db import MeetingMinutes, MeetingMinutesStatus
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.celery_tasks.meeting_minutes_heartbeat import _get_heartbeat_key

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create the Redis client for heartbeat checking."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


async def _cleanup_stale_meeting_minutes() -> None:
    """Mark PENDING/PROCESSING meeting-minutes rows with no heartbeat as FAILED."""
    try:
        redis_client = get_redis_client()
    except Exception as exc:
        logger.warning("Cannot reach Redis for meeting-minutes stale check: %s", exc)
        return

    async with get_celery_session_maker()() as session:
        result = await session.execute(
            select(MeetingMinutes.id).where(
                MeetingMinutes.status.in_(
                    [MeetingMinutesStatus.PENDING, MeetingMinutesStatus.PROCESSING]
                )
            )
        )
        in_progress_ids = result.scalars().all()

        if not in_progress_ids:
            logger.debug("No in-progress meeting-minutes rows found")
            return

        stale_ids = []
        for mm_id in in_progress_ids:
            try:
                if not redis_client.exists(_get_heartbeat_key(mm_id)):
                    stale_ids.append(mm_id)
            except Exception as exc:
                logger.warning(
                    "Redis heartbeat check failed for meeting minutes %s: %s",
                    mm_id,
                    exc,
                )
                # If we cannot talk to Redis for a single key, abort the whole
                # batch to avoid falsely marking rows as failed.
                return

        if stale_ids:
            logger.warning(
                "Marking %d stale meeting-minutes rows as failed: %s",
                len(stale_ids),
                stale_ids,
            )
            await session.execute(
                update(MeetingMinutes)
                .where(MeetingMinutes.id.in_(stale_ids))
                .values(
                    status=MeetingMinutesStatus.FAILED,
                    error="processing_task_interrupted",
                )
            )
            await session.commit()


@celery_app.task(name="cleanup_stale_meeting_minutes")
def cleanup_stale_meeting_minutes_task():
    """Celery entry point for stale meeting-minutes cleanup."""
    return run_async_celery_task(_cleanup_stale_meeting_minutes)
