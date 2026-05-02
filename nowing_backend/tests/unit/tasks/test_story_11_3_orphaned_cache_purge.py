"""Unit tests for Story 11.3: Automated Orphaned Cache Purge."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self, execute_return=None, execute_side_effect=None):
        self._execute_return = execute_return or MagicMock(rowcount=0)
        self._execute_side_effect = execute_side_effect
        self._call_idx = 0
        self.commit_count = 0
        self.executed_stmts = []

    async def execute(self, stmt, params=None):
        self.executed_stmts.append((stmt, params))
        if self._execute_side_effect is not None:
            value = self._execute_side_effect[self._call_idx]
            self._call_idx += 1
            return value
        return self._execute_return

    async def commit(self):
        self.commit_count += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


def _make_session_maker(session):
    def _maker():
        return session
    return _maker


@pytest.fixture(autouse=True)
def _bypass_idempotency_lock():
    """Most tests don't care about the Redis lock — patch it to always-acquired
    with no Redis client (no-op release)."""
    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._try_acquire_orphan_lock",
        new=AsyncMock(return_value=(True, None, None)),
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._release_orphan_lock",
        new=AsyncMock(return_value=None),
    ):
        yield


@pytest.mark.asyncio
async def test_ac1_cleanup_orphaned_snapshots_logic():
    """AC#2, AC#3: DELETE statement filters orphans correctly and commits."""
    delete_result = MagicMock(rowcount=5)
    session = _FakeSession(execute_return=delete_result)

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned
        await _async_cleanup_orphaned()

    # The first execute may be the SET LOCAL statement_timeout; find the DELETE.
    delete_stmt = None
    for stmt, _ in session.executed_stmts:
        s = str(stmt).lower()
        if "delete from crypto_data_snapshots" in s:
            delete_stmt = s
            break

    assert delete_stmt is not None
    assert "search_space_id is not null" in delete_stmt
    assert "not exists" in delete_stmt
    assert "order by id asc" in delete_stmt
    assert session.commit_count >= 1


@pytest.mark.asyncio
async def test_ac2_batch_deletion_three_batches():
    """AC#4 (per spec subtask 4.2): 2500 orphans -> 3 batches (1000+1000+500)."""
    # The first execute may be SET LOCAL statement_timeout (fake-DB no-op), so
    # provide enough side_effects to cover preamble + 3 deletes.
    preamble_no_op = MagicMock(rowcount=0)
    res_b1 = MagicMock(rowcount=1000)
    res_b2 = MagicMock(rowcount=1000)
    res_b3 = MagicMock(rowcount=500)

    session = _FakeSession(
        execute_side_effect=[preamble_no_op, res_b1, res_b2, res_b3]
    )

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned
        await _async_cleanup_orphaned()

    # 3 DELETEs (excluding the preamble statement_timeout SET).
    delete_count = sum(
        1 for stmt, _ in session.executed_stmts
        if "delete from crypto_data_snapshots" in str(stmt).lower()
    )
    assert delete_count == 3, f"expected 3 batched DELETEs, got {delete_count}"
    # Commit per batch.
    assert session.commit_count == 3


@pytest.mark.asyncio
async def test_ac3_cleanup_orphaned_snapshots_logs_json():
    """AC#5: structured JSON metric line is emitted with required fields + status."""
    delete_result = MagicMock(rowcount=10)
    session = _FakeSession(execute_return=delete_result)

    captured: list[str] = []

    def _capture(msg, *args, **kwargs):
        captured.append(msg)

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.metric_logger.info",
        side_effect=_capture,
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned
        await _async_cleanup_orphaned()

    # Exactly one metric line must be emitted regardless of success/failure.
    json_lines = [
        json.loads(line) for line in captured if line.strip().startswith("{")
    ]
    metric = next(
        (m for m in json_lines if m.get("task") == "cleanup_orphaned_snapshots"),
        None,
    )
    assert metric is not None, "expected a JSON metric line"
    assert metric["status"] == "completed"
    assert metric["deleted_count"] == 10
    assert "duration_ms" in metric
    assert isinstance(metric["duration_ms"], int)


@pytest.mark.asyncio
async def test_metric_emitted_on_failure_with_status_failed():
    """Round-2 review: exception path must emit `status=failed` + error field."""
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.execute.side_effect = RuntimeError("boom")
    session.commit = AsyncMock()

    captured: list[str] = []

    def _capture(msg, *args, **kwargs):
        captured.append(msg)

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=lambda: session,
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.metric_logger.info",
        side_effect=_capture,
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned
        with pytest.raises(RuntimeError):
            await _async_cleanup_orphaned()

    metric = next(
        (json.loads(line) for line in captured if line.strip().startswith("{")),
        None,
    )
    assert metric is not None
    assert metric["status"] == "failed"
    assert "error" in metric
    assert "RuntimeError" in metric["error"]


@pytest.mark.asyncio
async def test_idempotency_lock_skips_when_held():
    """Round-2 review: if another instance already holds the lock, skip and emit
    `status=skipped_locked` without touching the DB."""
    captured: list[str] = []

    def _capture(msg, *args, **kwargs):
        captured.append(msg)

    # Override the autouse fixture: simulate lock NOT acquired.
    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._try_acquire_orphan_lock",
        new=AsyncMock(return_value=(False, None, None)),
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
    ) as session_maker, patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.metric_logger.info",
        side_effect=_capture,
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned
        await _async_cleanup_orphaned()

    # Session maker must NOT be invoked when skipping.
    session_maker.assert_not_called()
    metric = next(
        (json.loads(line) for line in captured if line.strip().startswith("{")),
        None,
    )
    assert metric is not None
    assert metric["status"] == "skipped_locked"
    assert metric["deleted_count"] == 0


def test_ac1_beat_schedule_registered():
    """AC#1: weekly Sunday 4 AM UTC schedule is registered with sufficient expires."""
    from celery.schedules import crontab
    from app.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "crypto-cleanup-orphaned-snapshots" in schedule

    entry = schedule["crypto-cleanup-orphaned-snapshots"]
    assert entry["task"] == "crypto.cleanup_orphaned_snapshots"
    assert entry["schedule"] == crontab(hour=4, minute=0, day_of_week=0)
    # Round-2 review: weekly task expects same-day pickup, not 1-hour drop.
    assert entry["options"]["expires"] == 43200


def test_celery_global_timezone_is_utc():
    """Round-2 review: crontab(...) is interpreted in `celery_app.conf.timezone`.
    Pin to UTC globally (not per-schedule) to ensure 4 AM UTC means 4 AM UTC."""
    from app.celery_app import celery_app

    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True


def test_orphan_task_has_time_limits():
    """Round-2 review: `expires` only blocks unstarted tasks. A wall-clock guard
    via `time_limit`/`soft_time_limit` ensures a runaway task cannot hold row
    locks past the maintenance window."""
    from app.tasks.celery_tasks.crypto_refresh_tasks import (
        cleanup_orphaned_crypto_snapshots,
    )

    # Celery decorator stores limits on the task object.
    assert cleanup_orphaned_crypto_snapshots.time_limit == 5400
    assert cleanup_orphaned_crypto_snapshots.soft_time_limit == 4500


@pytest.mark.asyncio
async def test_ac6_runs_independently_of_cache_enabled():
    """AC#6: orphan cleanup must NOT check `_CACHE_ENABLED`. Patch the flag to
    False and verify the task still does its work."""
    delete_result = MagicMock(rowcount=3)
    session = _FakeSession(execute_return=delete_result)

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache._CACHE_ENABLED",
        False,
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup_orphaned
        await _async_cleanup_orphaned()

    # The task ran the DELETE despite cache being disabled.
    delete_count = sum(
        1 for stmt, _ in session.executed_stmts
        if "delete from crypto_data_snapshots" in str(stmt).lower()
    )
    assert delete_count == 1
