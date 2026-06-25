"""Unit tests for run_manager: mark_abandoned, cancel_run, start_run, resume_run."""

import asyncio
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_run_manager_state():
    """Guarantee run_manager module-level dicts are clean before and after each test."""
    from app.tasks.chat import run_manager as rm

    rm._active_runs.clear()
    rm._cancel_events.clear()
    yield
    rm._active_runs.clear()
    rm._cancel_events.clear()


# ---------------------------------------------------------------------------
# mark_abandoned_runs_on_startup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_abandoned_skipped_when_uvicorn_reload(monkeypatch):
    monkeypatch.setenv("UVICORN_RELOAD", "true")
    from app.tasks.chat import run_manager as rm
    count = await rm.mark_abandoned_runs_on_startup()
    assert count == 0


@pytest.mark.asyncio
async def test_mark_abandoned_skipped_when_flag_disabled(monkeypatch):
    with patch("app.tasks.chat.run_manager._RESUMABLE_RUNS_ENABLED", False):
        from app.tasks.chat import run_manager as rm
        count = await rm.mark_abandoned_runs_on_startup()
        assert count == 0


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

    async def _dummy():
        await event.wait()

    task = asyncio.create_task(_dummy())
    rm._active_runs[run_id] = task

    result = await rm.cancel_run(run_id)
    assert result is True
    assert event.is_set()


@pytest.mark.asyncio
async def test_cancel_run_falls_back_to_task_cancel_on_timeout():
    """If task doesn't stop cooperatively within 2s, task.cancel() is called."""
    from app.tasks.chat import run_manager as rm

    run_id = uuid4()
    event = asyncio.Event()
    rm._cancel_events[run_id] = event

    async def _stuck():
        try:
            await asyncio.sleep(999)
        except asyncio.CancelledError:
            raise

    task = asyncio.create_task(_stuck())
    rm._active_runs[run_id] = task

    async def _fast_timeout(coro, timeout):
        raise asyncio.TimeoutError()

    with patch("app.tasks.chat.run_manager.asyncio.wait_for", _fast_timeout):
        result = await rm.cancel_run(run_id)

    assert result is True
    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()


# ---------------------------------------------------------------------------
# _active_runs / _cancel_events: lifecycle tracking
# ---------------------------------------------------------------------------

def test_active_runs_dict_initially_empty():
    """Module-level dicts start empty (autouse fixture guarantees this)."""
    from app.tasks.chat import run_manager as rm
    assert isinstance(rm._active_runs, dict)
    assert len(rm._active_runs) == 0
    assert isinstance(rm._cancel_events, dict)
    assert len(rm._cancel_events) == 0


def test_cleanup_callback_removes_from_dicts():
    """Simulate the done-callback directly to verify it removes the run."""
    from app.tasks.chat import run_manager as rm

    run_id = uuid4()
    fake_task = MagicMock()
    rm._active_runs[run_id] = fake_task
    rm._cancel_events[run_id] = asyncio.Event()

    def _cleanup(t):
        rm._active_runs.pop(run_id, None)
        rm._cancel_events.pop(run_id, None)

    _cleanup(fake_task)

    assert run_id not in rm._active_runs
    assert run_id not in rm._cancel_events


# ---------------------------------------------------------------------------
# start_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_run_raises_503_when_disabled():
    """Feature flag off → start_run raises HTTPException(503)."""
    from fastapi import HTTPException

    with patch("app.tasks.chat.run_manager._RESUMABLE_RUNS_ENABLED", False):
        from app.tasks.chat.run_manager import start_run

        with pytest.raises(HTTPException) as exc_info:
            await start_run(
                thread_id=42,
                user_query="test",
                user_id=uuid4(),
                search_space_id=1,
            )
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_start_run_creates_run_and_spawns_task():
    """start_run persists a ChatRun row and spawns the execution task."""
    from app.tasks.chat import run_manager as rm

    user_id = uuid4()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.chat.run_manager._RESUMABLE_RUNS_ENABLED", True),
        patch(
            "app.tasks.chat.run_manager.shielded_async_session",
            return_value=mock_session,
        ),
        patch(
            "app.tasks.chat.run_manager._spawn_execution_task",
            new_callable=AsyncMock,
        ) as mock_spawn,
    ):
        run = await rm.start_run(
            thread_id=42,
            user_query="analyze BTC",
            user_id=user_id,
            search_space_id=1,
        )

    assert run.thread_id == 42
    assert run.user_query == "analyze BTC"
    assert run.created_by_id == user_id
    assert str(run.status) == "running"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_spawn.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_run_session_id_contains_thread_id():
    """Session ID format: {thread_id}-{run_id_hex_prefix}."""
    from app.tasks.chat import run_manager as rm

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.chat.run_manager._RESUMABLE_RUNS_ENABLED", True),
        patch(
            "app.tasks.chat.run_manager.shielded_async_session",
            return_value=mock_session,
        ),
        patch(
            "app.tasks.chat.run_manager._spawn_execution_task",
            new_callable=AsyncMock,
        ),
    ):
        run = await rm.start_run(
            thread_id=99,
            user_query="test",
            user_id=uuid4(),
            search_space_id=1,
        )

    assert run.session_id.startswith("99-")


# ---------------------------------------------------------------------------
# resume_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_run_raises_404_when_not_found():
    """resume_run raises 404 when run doesn't exist."""
    from fastapi import HTTPException

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "app.tasks.chat.run_manager.shielded_async_session",
            return_value=mock_session,
        ),
    ):
        from app.tasks.chat.run_manager import resume_run

        with pytest.raises(HTTPException) as exc_info:
            await resume_run(run_id=uuid4(), search_space_id=1)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_resume_run_raises_409_when_not_abandoned():
    """resume_run raises 409 when run status is not 'abandoned'."""
    from fastapi import HTTPException

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_row = {"status": "completed", "langgraph_thread_id": "lg-1"}
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch(
        "app.tasks.chat.run_manager.shielded_async_session",
        return_value=mock_session,
    ):
        from app.tasks.chat.run_manager import resume_run

        with pytest.raises(HTTPException) as exc_info:
            await resume_run(run_id=uuid4(), search_space_id=1)
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_resume_run_raises_409_when_no_checkpoint():
    """resume_run raises 409 when checkpoint is not resumable."""
    from fastapi import HTTPException

    run_id = uuid4()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_row = {"status": "abandoned", "langgraph_thread_id": "lg-1"}
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "app.tasks.chat.run_manager.shielded_async_session",
            return_value=mock_session,
        ),
        patch(
            "app.tasks.chat.run_manager._find_resumable_checkpoint",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        from app.tasks.chat.run_manager import resume_run

        with pytest.raises(HTTPException) as exc_info:
            await resume_run(run_id=run_id, search_space_id=1)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "checkpoint_not_resumable"


@pytest.mark.asyncio
async def test_resume_run_raises_503_on_checkpointer_unavailable():
    """resume_run raises 503 when checkpointer backend is broken."""
    from fastapi import HTTPException

    from app.tasks.chat.run_manager import CheckpointerUnavailableError

    run_id = uuid4()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_row = {"status": "abandoned", "langgraph_thread_id": "lg-1"}
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "app.tasks.chat.run_manager.shielded_async_session",
            return_value=mock_session,
        ),
        patch(
            "app.tasks.chat.run_manager._find_resumable_checkpoint",
            new_callable=AsyncMock,
            side_effect=CheckpointerUnavailableError("connection refused"),
        ),
    ):
        from app.tasks.chat.run_manager import resume_run

        with pytest.raises(HTTPException) as exc_info:
            await resume_run(run_id=run_id, search_space_id=1)
        assert exc_info.value.status_code == 503
