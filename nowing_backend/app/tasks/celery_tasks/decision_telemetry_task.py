"""Celery task for decision telemetry housekeeping (Story 39.7).

``evaluate_decision_daily_cost_alert`` runs the same deduped cost-alert
check the admin dashboard performs on read — so a daily-cost breach fires
an ``AdminHealthAlert`` even when nobody opens the dashboard.
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.tasks.celery_tasks import run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(
    name="evaluate_decision_daily_cost_alert",
    bind=True,
    default_retry_delay=60,
    max_retries=2,
)
def evaluate_decision_daily_cost_alert_task(self) -> dict:
    """Every-15-min check: today's UTC decision spend vs the alert threshold."""

    async def _check() -> dict:
        from app.db import async_session_maker
        from app.services.admin_telemetry.service import AdminTelemetryService

        async with async_session_maker() as session:
            return await AdminTelemetryService(session).check_daily_cost_alert()

    try:
        return run_async_celery_task(_check)
    except Exception as exc:  # retry-eligible failure
        raise self.retry(exc=exc) from exc
