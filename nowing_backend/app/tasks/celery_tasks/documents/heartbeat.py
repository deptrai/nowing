"""Document heartbeat helpers."""


import asyncio
import logging

from app.config import config
from app.observability import metrics as ot_metrics

logger = logging.getLogger(__name__)

# ===== Redis heartbeat for document processing tasks =====
# Same mechanism as connector indexing heartbeats (app/routes/connectors/_shared.py).
# A background coroutine refreshes a Redis key every 60s with a 2-min TTL.
# If the Celery worker crashes, the coroutine dies, the key expires, and the
# stale_notification_cleanup_task detects the missing key and marks the
# notification + document as failed.
_doc_heartbeat_redis = None
HEARTBEAT_TTL_SECONDS = 120  # 2 minutes — same as connector indexing
HEARTBEAT_REFRESH_INTERVAL = 60  # Refresh every 60 seconds



def _get_doc_heartbeat_redis():
    """Get Redis client for document processing heartbeat."""
    import redis

    global _doc_heartbeat_redis
    if _doc_heartbeat_redis is None:
        _doc_heartbeat_redis = redis.from_url(
            config.REDIS_APP_URL, decode_responses=True
        )
    return _doc_heartbeat_redis


def _get_heartbeat_key(notification_id: int) -> str:
    """Generate Redis key for document processing heartbeat.

    Uses same key pattern as connector indexing: indexing:heartbeat:{notification_id}
    """
    return f"indexing:heartbeat:{notification_id}"


def _start_heartbeat(notification_id: int) -> None:
    """Set initial Redis heartbeat key for a document processing task."""
    try:
        key = _get_heartbeat_key(notification_id)
        _get_doc_heartbeat_redis().setex(key, HEARTBEAT_TTL_SECONDS, "started")
        ot_metrics.record_celery_heartbeat_refresh(heartbeat_type="document")
    except Exception as e:
        ot_metrics.record_celery_heartbeat_failure(heartbeat_type="document")
        logger.warning(
            f"Failed to set initial heartbeat for notification {notification_id}: {e}"
        )


def _stop_heartbeat(notification_id: int) -> None:
    """Delete Redis heartbeat key when task completes (success or failure)."""
    try:
        key = _get_heartbeat_key(notification_id)
        _get_doc_heartbeat_redis().delete(key)
    except Exception:
        pass  # Key will expire on its own


async def _run_heartbeat_loop(notification_id: int):
    """Background coroutine that refreshes Redis heartbeat every 60 seconds.

    This keeps the heartbeat alive while the task is running.
    When the task finishes, this coroutine is cancelled via heartbeat_task.cancel().
    When the worker crashes, this coroutine dies with it and the key expires.
    """
    key = _get_heartbeat_key(notification_id)
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_REFRESH_INTERVAL)
            try:
                _get_doc_heartbeat_redis().setex(key, HEARTBEAT_TTL_SECONDS, "alive")
                ot_metrics.record_celery_heartbeat_refresh(heartbeat_type="document")
            except Exception as e:
                ot_metrics.record_celery_heartbeat_failure(heartbeat_type="document")
                logger.warning(
                    f"Failed to refresh heartbeat for notification {notification_id}: {e}"
                )
    except asyncio.CancelledError:
        pass  # Normal cancellation when task completes
