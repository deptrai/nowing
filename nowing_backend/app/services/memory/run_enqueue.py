"""The single run-completion seam for memory extraction (Story 3.13, T4/D1).

Both doors (REST sync, REST async, agent sync) call
:func:`enqueue_run_memory_extraction_after_commit` *after* the recorder has
returned and committed its ``runs`` row. Keeping the seam in one function is what
keeps the 15 capability executors untouched: there is no per-platform callback and
no duplicated logic between REST and agent, or between sync and async.

Three properties this module is responsible for:

* **After the commit, never inside it (D1/D2).** The task only receives a run id,
  so it must not be queued before the row it names is visible to another
  connection. Callers invoke this only on a recorder success return.
* **Never changes the capability result (AC-5).** Every failure here — broker
  down, serialization error, anything — is logged and swallowed. A scrape that
  succeeded stays successful and its output stays readable.
* **Only successful runs (D1).** ``failed``/``cancelled``/``running`` never
  enqueue. The status check lives here rather than in each caller so a new door
  cannot forget it.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# D1: only a committed successful run may produce memory.
_ELIGIBLE_STATUS = "success"


def _normalize_run_id(run_id: str) -> str:
    """Strip the ``run_`` display prefix the doors hand around.

    The REST door sets ``X-Run-Id: run_<uuid>`` and the agent door embeds the same
    shape in its tool payload, so both prefixed and bare ids reach this seam. The
    Celery task takes the bare UUID string.
    """
    return run_id[len("run_") :] if run_id.startswith("run_") else run_id


def enqueue_run_memory_extraction_after_commit(
    run_id: str | None, *, status: str = _ELIGIBLE_STATUS
) -> bool:
    """Queue background memory extraction for a committed successful run.

    Returns ``True`` when a task was queued. Never raises: the caller has already
    produced a successful capability response and this is optional background
    work (AC-5).

    ``run_id`` is ``None`` when the best-effort recorder failed; there is then no
    durable run to extract from, and no idempotency anchor either, so there is
    nothing to enqueue.
    """
    if run_id is None:
        return False
    if status != _ELIGIBLE_STATUS:
        return False

    try:
        from app.observability.metrics import record_run_memory_enqueued
        from app.tasks.celery_tasks.run_memory_extraction_task import (
            extract_memory_after_run,
        )

        extract_memory_after_run.delay(_normalize_run_id(run_id))
        record_run_memory_enqueued()
        return True
    except Exception:
        # Broker unreachable, serialization failure, import-time error: all
        # non-events for the caller. Logged at exception level because a
        # persistently unreachable broker means first-run value is silently not
        # being delivered, which is worth an alert even though it is not an error
        # for this request.
        logger.exception(
            "enqueue_run_memory_extraction failed run_id=%s (capability result unaffected)",
            run_id,
        )
        return False


__all__ = ["enqueue_run_memory_extraction_after_commit"]
