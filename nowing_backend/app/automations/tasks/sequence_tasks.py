"""Celery tasks for sequence evaluation and step execution (Story 24.1 / AD-39)."""

from __future__ import annotations

import logging
from uuid import UUID

from app.celery_app import celery_app
from app.services.sequencer_service import SequencerService
from app.tasks.celery_tasks import (
    get_celery_session_maker,
    run_async_celery_task,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="evaluate_sequences")
def evaluate_sequences() -> int:
    """Periodic Celery Beat task to query and dispatch due sequence enrollments."""
    return run_async_celery_task(_evaluate_sequences_impl)


async def _evaluate_sequences_impl() -> int:
    sequencer = SequencerService()
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        try:
            return await sequencer.evaluate_pending_enrollments(session)
        except Exception:
            logger.exception("Error evaluating pending sequence enrollments")
            return 0


@celery_app.task(name="execute_sequence_step", bind=True, max_retries=3, default_retry_delay=60)
def execute_sequence_step(self, enrollment_id: str, workspace_id: int) -> None:
    """Execute a single sequence step for an enrollment."""
    return run_async_celery_task(lambda: _execute_sequence_step_impl(enrollment_id, workspace_id))


async def _execute_sequence_step_impl(enrollment_id_str: str, workspace_id: int) -> None:
    from app.canonical.tenant_context import set_request_tenant_context

    sequencer = SequencerService()
    session_maker = get_celery_session_maker()
    enrollment_id = UUID(enrollment_id_str)
    async with session_maker() as session:
        # Set workspace GUC for audit/RLS. Celery worker should use a DB role with BYPASSRLS
        # because sequence execution does not know the client_id before loading the row.
        await set_request_tenant_context(session, workspace_id=workspace_id)
        try:
            await sequencer.execute_enrollment_step(
                session=session,
                enrollment_id=enrollment_id,
                workspace_id=workspace_id,
            )
        except Exception:
            logger.exception("Error executing sequence step for enrollment %s", enrollment_id)
            await session.rollback()
            raise
