"""Celery worker for processing meeting minutes."""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select

from app.celery_app import celery_app
from app.db import MeetingMinutes, MeetingMinutesStatus
from app.services.meeting_minutes.service import MeetingMinutesService
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.celery_tasks.meeting_minutes_heartbeat import (
    meeting_minutes_heartbeat_is_alive,
    run_meeting_minutes_heartbeat_loop,
    start_meeting_minutes_heartbeat,
    stop_meeting_minutes_heartbeat,
)

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    try:
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        logger.warning(
            "WindowsProactorEventLoopPolicy is unavailable; async subprocess support may fail."
        )


_TERMINAL_STATUSES = {
    MeetingMinutesStatus.READY,
    MeetingMinutesStatus.DEGRADED,
    MeetingMinutesStatus.FAILED,
    MeetingMinutesStatus.VALIDATION_FAILED,
}


@celery_app.task(
    name="process_meeting_minutes",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def process_meeting_minutes(
    self,
    meeting_minutes_id: int,
    workspace_id: int,
    user_id: str,
) -> dict:
    """Celery task to process a meeting minutes request."""
    try:
        return run_async_celery_task(
            lambda: _process_meeting_minutes(
                meeting_minutes_id,
                workspace_id,
                user_id,
                celery_task_id=str(self.request.id or ""),
            )
        )
    except Exception as exc:
        error = str(exc)
        logger.error("Error processing meeting minutes %s: %s", meeting_minutes_id, error)
        try:
            run_async_celery_task(
                lambda: _mark_meeting_minutes_failed(meeting_minutes_id, error)
            )
        except Exception:
            logger.exception(
                "Failed to mark meeting minutes %s as failed", meeting_minutes_id
            )
        return {"status": "failed", "meeting_minutes_id": meeting_minutes_id, "error": error}


async def _mark_meeting_minutes_failed(meeting_minutes_id: int, error: str) -> None:
    async with get_celery_session_maker()() as session:
        row = (
            await session.execute(
                select(MeetingMinutes).where(MeetingMinutes.id == meeting_minutes_id)
            )
        ).scalar_one_or_none()
        if row:
            row.status = MeetingMinutesStatus.FAILED
            row.error = error
            await session.commit()


async def _process_meeting_minutes(
    meeting_minutes_id: int,
    workspace_id: int,
    user_id: str,
    celery_task_id: str,
) -> dict:
    """Async worker entry point with Redis heartbeat and dead-task takeover."""
    async with get_celery_session_maker()() as session:
        row = (
            await session.execute(
                select(MeetingMinutes).where(MeetingMinutes.id == meeting_minutes_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return {
                "status": "failed",
                "meeting_minutes_id": meeting_minutes_id,
                "error": "not_found",
            }

        # Terminal rows should never be re-processed.
        if row.status in _TERMINAL_STATUSES:
            return {
                "status": row.status.value,
                "meeting_minutes_id": row.id,
            }

        # Idempotency / dead-task takeover.
        if row.processing_task_id and row.processing_task_id != celery_task_id:
            if meeting_minutes_heartbeat_is_alive(meeting_minutes_id):
                # Another worker is still alive and owns this row.
                return {
                    "status": row.status.value,
                    "meeting_minutes_id": row.id,
                }
            logger.info(
                "MeetingMinutes %s taking over from dead task %s",
                row.id,
                row.processing_task_id,
            )

        row.processing_task_id = celery_task_id
        await session.commit()

    heartbeat_task = None
    try:
        start_meeting_minutes_heartbeat(meeting_minutes_id)
        heartbeat_task = asyncio.create_task(
            run_meeting_minutes_heartbeat_loop(meeting_minutes_id)
        )

        async with get_celery_session_maker()() as session:
            service = MeetingMinutesService()
            result = await service.process(
                session,
                meeting_minutes_id,
                processing_task_id=celery_task_id,
            )
            return result.model_dump()
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        stop_meeting_minutes_heartbeat(meeting_minutes_id)
