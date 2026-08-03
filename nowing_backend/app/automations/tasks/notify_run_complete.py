"""Celery task that notifies a user when an automation run completes."""

from __future__ import annotations

import logging

from app.automations.services.telegram_notifications import (
    send_automation_run_telegram_notification,
)
from app.celery_app import celery_app
from app.tasks.celery_tasks import (
    get_celery_session_maker,
    run_async_celery_task,
)

logger = logging.getLogger(__name__)

TASK_NAME = "automation.notify_telegram_run_complete"


@celery_app.task(
    name=TASK_NAME,
    bind=True,
    soft_time_limit=180,
    time_limit=300,
)
def notify_telegram_run_complete(self, run_id: int) -> None:
    """Notify the automation owner that a run has finished.

    In-app notifications are always created. Telegram delivery is gated by the
    user's notification preferences and an active Telegram binding.
    """
    return run_async_celery_task(lambda: _impl(run_id))


async def _impl(run_id: int) -> None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        try:
            await send_automation_run_telegram_notification(session, run_id)
        except Exception:
            logger.exception(
                "Failed to process automation run notification for run %d", run_id
            )
            await session.rollback()
