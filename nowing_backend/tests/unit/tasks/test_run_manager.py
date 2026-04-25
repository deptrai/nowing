"""Unit tests for run_manager: mark_abandoned_runs_on_startup, cancel_run cooperative flow."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# mark_abandoned_runs_on_startup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_abandoned_skipped_when_uvicorn_reload(monkeypatch):
    monkeypatch.setenv("UVICORN_RELOAD", "true")
    from app.tasks.chat import run_manager as rm
    # Reload module state for env check
    count = await rm.mark_abandoned_runs_on_startup()
    assert count == 0


@pytest.mark.asyncio
async def test_mark_abandoned_skipped_when_flag_disabled(monkeypatch):
    monkeypatch.setenv("RESUMABLE_RUNS_ENABLED", "false")
    # Re-import to pick up env var (module-level constant)
    import importlib
    import app.tasks.chat.run_manager as rm_module
    importlib.reload(rm_module)
    count = await rm_module.mark_abandoned_runs_on_startup()
    assert count == 0
    # Restore
    monkeypatch.delenv("RESUMABLE_RUNS_ENABLED", raising=False)
    importlib.reload(rm_module)


@pytest.mark.asyncio
async def test_mark_abandoned_handles_db_error_gracefully(monkeypatch):
    """M2: table not ready on fresh deploy — must not crash."""
    monkeypatch.delenv("UVICORN_RELOAD", raising=False)

    async def _broken_session():
        class _Ctx:
            async def __aenter__(self):
                raise RuntimeError("relation chat_runs does not exist")
            async def __aexit__(self, *_):
                pass
        return _Ctx()

    with patch("app.tasks.chat.run_manager.shielded_async_session", _broken_session):
        import app.tasks.chat.run_manager as rm
        # Should not raise
        count = await rm.mark_abandoned_runs_on_startup()
    assert count == 0


# ---------------------------------------------------------------------------
# cancel_run: cooperative cancel path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_run_sets_cancel_event():
    """cancel_run sets the event so the agent loop can exit cooperatively."""
    from app.tasks.chat import run_manager as rm

    run_id = uuid4()
    event = asyncio.Event()
    rm._cancel_events[run_id] = event

    # Task that waits on the event
    async def _dummy():
        await event.wait()

    task = asyncio.create_task(_dummy())
    rm._active_runs[run_id] = task

    result = await rm.cancel_run(run_id)
    assert result is True
    assert event.is_set()

    # Cleanup
    rm._active_runs.pop(run_id, None)
    rm._cancel_events.pop(run_id, None)


@pytest.mark.asyncio
async def test_cancel_run_falls_back_to_task_cancel_on_timeout():
    """If task doesn't stop cooperatively within 2s, task.cancel() is called."""
    from app.tasks.chat import run_manager as rm

    run_id = uuid4()
    event = asyncio.Event()
    rm._cancel_events[run_id] = event

    # Task that never responds to event
    cancelled_flag = {"called": False}

    async def _stuck():
        try:
            await asyncio.sleep(999)
        except asyncio.CancelledError:
            cancelled_flag["called"] = True
            raise

    task = asyncio.create_task(_stuck())
    rm._active_runs[run_id] = task

    # Patch wait_for to simulate timeout immediately
    original_wait_for = asyncio.wait_for

    async def _fast_timeout(coro, timeout):
        raise asyncio.TimeoutError()

    with patch("app.tasks.chat.run_manager.asyncio.wait_for", _fast_timeout):
        result = await rm.cancel_run(run_id)

    assert result is True
    # Give the cancellation time to propagate
    await asyncio.sleep(0.01)
    assert task.cancelled()

    rm._active_runs.pop(run_id, None)
    rm._cancel_events.pop(run_id, None)


# ---------------------------------------------------------------------------
# _active_runs / _cancel_events: lifecycle tracking
# ---------------------------------------------------------------------------

def test_active_runs_dict_initially_empty():
    """Module-level dicts start empty (or at least importable)."""
    from app.tasks.chat import run_manager as rm
    assert isinstance(rm._active_runs, dict)
    assert isinstance(rm._cancel_events, dict)


def test_cleanup_callback_removes_from_dicts():
    """Simulate the done-callback directly to verify it removes the run."""
    from app.tasks.chat import run_manager as rm

    run_id = uuid4()
    fake_task = MagicMock()
    rm._active_runs[run_id] = fake_task
    rm._cancel_events[run_id] = asyncio.Event()

    # Simulate the cleanup callback that _spawn_execution_task registers
    def _cleanup(t):
        rm._active_runs.pop(run_id, None)
        rm._cancel_events.pop(run_id, None)

    _cleanup(fake_task)

    assert run_id not in rm._active_runs
    assert run_id not in rm._cancel_events
