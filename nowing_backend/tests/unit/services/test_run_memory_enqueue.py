"""The run-completion seam for memory extraction (Story 3.13, T4 / D1, AC-5).

The seam itself is tiny, and the properties worth pinning are exactly the ones
that are easy to regress in a refactor:

* only ``success`` enqueues — ``error``/``cancelled``/``running`` never do (D1);
* a ``None`` run id (best-effort recorder failed) never enqueues, because there
  is no durable row to extract from and no idempotency anchor;
* the ``run_`` display prefix the doors pass around is stripped, since the task
  takes a bare UUID;
* a broker failure is swallowed — a successful capability response must not turn
  into an error because optional background work could not be queued (AC-5).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def seam(monkeypatch):
    """Patch the Celery task and the metric out of the seam's lazy imports.

    The seam imports both *inside* the function, so patching the source modules
    (rather than an attribute on the seam) is what actually intercepts them.
    """
    import app.observability.metrics as metrics_mod
    import app.tasks.celery_tasks.run_memory_extraction_task as task_mod
    from app.services.memory import run_enqueue

    delay = MagicMock()
    monkeypatch.setattr(task_mod.extract_memory_after_run, "delay", delay)
    counter = MagicMock()
    monkeypatch.setattr(metrics_mod, "record_run_memory_enqueued", counter)
    return run_enqueue, delay, counter


def test_success_run_is_enqueued_with_bare_uuid(seam):
    run_enqueue, delay, counter = seam
    run_id = str(uuid.uuid4())

    assert run_enqueue.enqueue_run_memory_extraction_after_commit(run_id) is True
    delay.assert_called_once_with(run_id)
    counter.assert_called_once()


def test_run_prefix_is_stripped(seam):
    run_enqueue, delay, _ = seam
    raw = str(uuid.uuid4())

    assert run_enqueue.enqueue_run_memory_extraction_after_commit(f"run_{raw}") is True
    delay.assert_called_once_with(raw)


@pytest.mark.parametrize("status", ["error", "cancelled", "running", "pending"])
def test_non_success_status_never_enqueues(seam, status):
    """D1: only a committed successful run may produce memory."""
    run_enqueue, delay, counter = seam

    result = run_enqueue.enqueue_run_memory_extraction_after_commit(
        str(uuid.uuid4()), status=status
    )

    assert result is False
    delay.assert_not_called()
    counter.assert_not_called()


def test_missing_run_id_never_enqueues(seam):
    """The recorder is best-effort; ``None`` means there is no run to extract."""
    run_enqueue, delay, _ = seam

    assert run_enqueue.enqueue_run_memory_extraction_after_commit(None) is False
    delay.assert_not_called()


def test_broker_failure_is_swallowed(seam):
    """AC-5: enqueue failure must not surface to the capability caller."""
    run_enqueue, delay, _ = seam
    delay.side_effect = RuntimeError("broker unreachable")

    # No raise, and a falsey result so callers can log/metric if they care.
    assert run_enqueue.enqueue_run_memory_extraction_after_commit(str(uuid.uuid4())) is False
