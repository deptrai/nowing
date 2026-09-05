"""Celery task to purge expired admin health history records.

The default retention window is 30 days, configurable via
``ADMIN_HEALTH_HISTORY_RETENTION_DAYS``. This keeps the time-series
``admin_health_history`` table from growing unbounded while preserving
enough history for alert deduplication and 15-minute rolling rates.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.celery_app import celery_app
from app.models.admin_health import AdminHealthHistory
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 30


@celery_app.task(name="cleanup_admin_health_history")
def cleanup_admin_health_history() -> dict[str, int]:
    """Delete admin health history rows older than the retention window."""
    return run_async_celery_task(_cleanup_health_history)


async def _cleanup_health_history() -> dict[str, int]:
    async with get_celery_session_maker()() as session:
        try:
            from app.config import config

            retention_days = getattr(
                config, "ADMIN_HEALTH_HISTORY_RETENTION_DAYS", DEFAULT_RETENTION_DAYS
            )
            cutoff = datetime.now(UTC) - timedelta(days=int(retention_days))

            stmt = delete(AdminHealthHistory).where(AdminHealthHistory.probe_at < cutoff)
            result = await session.execute(stmt)
            deleted = result.rowcount

            await session.commit()
            logger.info(
                "Purged %s admin_health_history rows older than %s days",
                deleted,
                retention_days,
            )
            return {"deleted": deleted, "retention_days": retention_days}
        except Exception as exc:
            logger.error("Failed to purge admin health history: %s", exc, exc_info=True)
            await session.rollback()
            return {"deleted": 0, "error": str(exc)}
