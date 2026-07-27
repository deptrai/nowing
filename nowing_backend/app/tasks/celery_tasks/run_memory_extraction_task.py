"""Celery task that extracts durable memory from a completed run (Story 3.13, T3).

Mirrors ``memory_extraction_task.py`` (the chat-turn task) in shape, with the two
run-path requirements the story adds:

* **Claim before the LLM (D6/AC-6).** Celery delivery is at-least-once and two
  workers can start on the same run concurrently, so the task compare-and-sets
  ``Run.memory_extraction_status`` from ``NULL`` to ``pending`` in its own
  committed statement *before* any LLM call. Exactly one worker wins the CAS; the
  loser returns without calling the LLM.
* **Transient failures release the claim.** ``autoretry_for`` re-runs the task
  after a transient LLM/network error, and a retry must not be locked out by the
  ``pending`` marker its own earlier attempt wrote. The claim is therefore
  released back to ``NULL`` before the exception propagates. When the retry
  budget is exhausted the task writes the terminal ``failed`` marker instead.

Known limitation (deliberately not overclaimed): a worker that dies *hard* mid
LLM call — SIGKILL, OOM, container eviction — leaves ``pending`` behind with no
release, and this task has no staleness clock to reclaim it (``Run`` carries only
``created_at``; there is no ``updated_at``). The run is then never extracted.
That fails safe in the directions that cost money or corrupt data (no duplicate
memory, no duplicate ``memory_create`` charge, no duplicate event) and is bounded
to one lost extraction, but it is a real gap, not exactly-once delivery.
"""

from __future__ import annotations

import logging

from sqlalchemy import update

from app.celery_app import celery_app
from app.services.memory.pipeline import TRANSIENT_LLM_ERRORS
from app.services.memory.run_extraction import (
    STATUS_FAILED,
    STATUS_PENDING,
    RunMemoryExtractionService,
)
from app.tasks.celery_tasks import run_async_celery_task

logger = logging.getLogger(__name__)


async def _claim_run(session, run_id) -> bool:
    """CAS ``NULL -> pending`` for ``run_id``; ``True`` if this worker won.

    A single UPDATE with the old value in the WHERE clause is the whole mutual
    exclusion: Postgres serialises the two row writes, so of two concurrent
    workers exactly one sees ``rowcount == 1``. Committed immediately — holding
    the claim inside the extraction transaction would make the *other* worker
    block on the row lock until the LLM call finished, instead of returning at
    once.
    """
    from app.db import Run

    result = await session.execute(
        update(Run)
        .where(
            Run.id == run_id,
            Run.status == "success",
            Run.memory_extraction_status.is_(None),
        )
        .values(memory_extraction_status=STATUS_PENDING)
    )
    await session.commit()
    return result.rowcount == 1


async def _release_claim(session, run_id) -> None:
    """Return a ``pending`` claim to ``NULL`` so an autoretry can re-claim it."""
    from app.db import Run

    await session.execute(
        update(Run)
        .where(Run.id == run_id, Run.memory_extraction_status == STATUS_PENDING)
        .values(memory_extraction_status=None)
    )
    await session.commit()


async def _mark_failed(session, run_id) -> None:
    """Terminal ``failed`` marker: the retry budget is exhausted."""
    from datetime import UTC, datetime

    from app.db import Run

    await session.execute(
        update(Run)
        .where(Run.id == run_id, Run.memory_extraction_status == STATUS_PENDING)
        .values(
            memory_extraction_status=STATUS_FAILED,
            memory_extraction_completed_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _extract_memory_after_run(run_id, *, retries_left: bool = True) -> None:
    """Claim, extract, and release/mark on failure. Own session (D2)."""
    from app.tasks.celery_tasks import get_celery_session_maker

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        if not await _claim_run(session, run_id):
            # Either another worker holds the claim, or the run already reached a
            # terminal verdict. Both mean: do not call the LLM. The service's own
            # terminal/`source_run_id` guards cover the redelivery case.
            logger.debug("Run %s extraction not claimed by this worker", run_id)
            return

        service = RunMemoryExtractionService(session=session)
        try:
            await service.extract_from_run(run_id)
        except TRANSIENT_LLM_ERRORS:
            # The service may already have staged memory/usage writes. Roll them
            # back *before* releasing or terminalising the durable claim;
            # otherwise the marker's commit could accidentally commit a partial
            # batch (AC-5).
            await session.rollback()
            # Release so `autoretry_for` can re-claim on the next attempt; write
            # the terminal `failed` marker once the budget is gone.
            if retries_left:
                await _release_claim(session, run_id)
            else:
                await _mark_failed(session, run_id)
            raise
        except Exception:
            # Terminal (auth/config/validation/persistence): no retry would help.
            # Roll back the extraction transaction before committing `failed`,
            # so a fact staged before a later failure can never leak through.
            await session.rollback()
            await _mark_failed(session, run_id)
            raise


@celery_app.task(
    name="extract_memory_after_run",
    bind=True,
    autoretry_for=TRANSIENT_LLM_ERRORS,
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def extract_memory_after_run(self, run_id: str) -> None:
    """Best-effort memory extraction after a successful capability run."""
    from uuid import UUID

    run_uuid = UUID(run_id)
    max_retries = self.max_retries if self.max_retries is not None else 0
    retries_left = self.request.retries < max_retries
    return run_async_celery_task(
        lambda: _extract_memory_after_run(run_uuid, retries_left=retries_left)
    )
