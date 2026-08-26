"""Redis heartbeat helpers for meeting-minutes Celery tasks.

Active workers refresh a short-lived Redis key while they own a row.
If the worker crashes or is killed, the key expires and a periodic cleanup
task marks the stuck row as failed so the UI does not hang forever.
"""

from __future__ import annotations

import asyncio
import logging

import redis

from app.config import config
from app.observability import metrics as ot_metrics

logger = logging.getLogger(__name__)

_mm_heartbeat_redis: redis.Redis | None = None

HEARTBEAT_TTL_SECONDS = 120
HEARTBEAT_REFRESH_INTERVAL = 60
PENDING_HEARTBEAT_TTL_SECONDS = 600  # 10 minutes for rows not yet picked up by a worker


def _get_heartbeat_redis() -> redis.Redis:
    """Get or create the Redis client used for meeting-minutes heartbeats."""
    global _mm_heartbeat_redis
    if _mm_heartbeat_redis is None:
        _mm_heartbeat_redis = redis.from_url(
            config.REDIS_APP_URL, decode_responses=True
        )
    return _mm_heartbeat_redis


def _get_heartbeat_key(meeting_minutes_id: int) -> str:
    """Generate the Redis key for a meeting-minutes heartbeat."""
    return f"meeting_minutes:heartbeat:{meeting_minutes_id}"


def start_meeting_minutes_pending_heartbeat(meeting_minutes_id: int) -> None:
    """Set a long-lived heartbeat when a row is created but not yet started.

    This gives workers a grace window to pick the task up before a cleanup
    task decides the job is orphaned.
    """
    try:
        key = _get_heartbeat_key(meeting_minutes_id)
        _get_heartbeat_redis().setex(
            key, PENDING_HEARTBEAT_TTL_SECONDS, "pending"
        )
        ot_metrics.record_celery_heartbeat_refresh(heartbeat_type="meeting_minutes")
    except Exception as exc:
        ot_metrics.record_celery_heartbeat_failure(heartbeat_type="meeting_minutes")
        logger.warning(
            "Failed to set pending heartbeat for meeting minutes %s: %s",
            meeting_minutes_id,
            exc,
        )


def start_meeting_minutes_heartbeat(meeting_minutes_id: int) -> None:
    """Set the initial short-lived heartbeat when a worker starts processing."""
    try:
        key = _get_heartbeat_key(meeting_minutes_id)
        _get_heartbeat_redis().setex(key, HEARTBEAT_TTL_SECONDS, "started")
        ot_metrics.record_celery_heartbeat_refresh(heartbeat_type="meeting_minutes")
    except Exception as exc:
        ot_metrics.record_celery_heartbeat_failure(heartbeat_type="meeting_minutes")
        logger.warning(
            "Failed to set initial heartbeat for meeting minutes %s: %s",
            meeting_minutes_id,
            exc,
        )


def stop_meeting_minutes_heartbeat(meeting_minutes_id: int) -> None:
    """Delete the heartbeat key when the task finishes or fails."""
    try:
        key = _get_heartbeat_key(meeting_minutes_id)
        _get_heartbeat_redis().delete(key)
    except Exception:
        pass  # Key will expire on its own


def meeting_minutes_heartbeat_is_alive(meeting_minutes_id: int) -> bool:
    """Return True if a heartbeat key currently exists for the row."""
    try:
        return bool(
            _get_heartbeat_redis().exists(_get_heartbeat_key(meeting_minutes_id))
        )
    except Exception:
        return False


async def run_meeting_minutes_heartbeat_loop(meeting_minutes_id: int) -> None:
    """Background coroutine that refreshes the Redis heartbeat every 60 seconds.

    This keeps the heartbeat alive while the worker is alive.  When the task
    finishes, the coroutine is cancelled.  When the worker crashes, the
    coroutine dies and the key expires.
    """
    key = _get_heartbeat_key(meeting_minutes_id)
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_REFRESH_INTERVAL)
            try:
                _get_heartbeat_redis().setex(key, HEARTBEAT_TTL_SECONDS, "alive")
                ot_metrics.record_celery_heartbeat_refresh(
                    heartbeat_type="meeting_minutes"
                )
            except Exception as exc:
                ot_metrics.record_celery_heartbeat_failure(
                    heartbeat_type="meeting_minutes"
                )
                logger.warning(
                    "Failed to refresh heartbeat for meeting minutes %s: %s",
                    meeting_minutes_id,
                    exc,
                )
    except asyncio.CancelledError:
        pass
