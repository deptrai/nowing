"""Celery Beat task for sweeping expired human takeover missions (Story 32.1)."""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

TASK_NAME = "dsh_sweep_expired_takeovers"
_SWEEP_TIMEOUT_SECONDS = 900  # 15 minutes


@celery_app.task(name=TASK_NAME)
def dsh_sweep_expired_takeovers() -> None:
    """Beat tick: find and abort missions stuck in waiting_for_human past TTL."""

    async def _sweep() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            try:
                from app.services.dsh_mission_service import DshMissionService

                service = DshMissionService()
                swept = await service.sweep_expired_takeovers(
                    session, timeout_seconds=_SWEEP_TIMEOUT_SECONDS
                )
                await session.commit()
                if swept:
                    logger.info(
                        "dsh_sweep_expired_takeovers swept %d missions",
                        len(swept),
                    )
            except Exception:
                logger.exception("dsh_sweep_expired_takeovers_failed")

    run_async_celery_task(_sweep)
