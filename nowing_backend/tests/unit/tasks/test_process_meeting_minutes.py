"""Unit tests for the meeting-minutes Celery worker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.db import MeetingMinutesStatus
from app.tasks.process_meeting_minutes import _process_meeting_minutes


@pytest.mark.unit
async def test_process_skips_terminal_rows():
    """A terminal row must not be re-processed."""
    row = MagicMock()
    row.id = 1
    row.status = MeetingMinutesStatus.READY
    row.processing_task_id = None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    with patch(
        "app.tasks.process_meeting_minutes.get_celery_session_maker",
        return_value=lambda: MagicMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=False),
        ),
    ):
        result = await _process_meeting_minutes(1, 1, "u", "task-1")

    assert result["status"] == "ready"
    assert result["meeting_minutes_id"] == 1


@pytest.mark.unit
async def test_process_takes_over_dead_worker():
    """A new worker takes over a PROCESSING row whose heartbeat has expired."""
    row = MagicMock()
    row.id = 2
    row.status = MeetingMinutesStatus.PROCESSING
    row.processing_task_id = "old-task"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    service_result = MagicMock()
    service_result.model_dump.return_value = {
        "meeting_minutes_id": 2,
        "status": "ready",
    }

    with (
        patch(
            "app.tasks.process_meeting_minutes.get_celery_session_maker",
            return_value=lambda: MagicMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ) as _,
        patch(
            "app.tasks.process_meeting_minutes.meeting_minutes_heartbeat_is_alive",
            return_value=False,
        ),
        patch(
            "app.tasks.process_meeting_minutes.start_meeting_minutes_heartbeat"
        ) as mock_start,
        patch(
            "app.tasks.process_meeting_minutes.run_meeting_minutes_heartbeat_loop",
            new_callable=AsyncMock,
        ) as mock_loop,
        patch(
            "app.tasks.process_meeting_minutes.stop_meeting_minutes_heartbeat"
        ) as mock_stop,
        patch(
            "app.tasks.process_meeting_minutes.MeetingMinutesService.process",
            new_callable=AsyncMock,
            return_value=service_result,
        ),
    ):
        result = await _process_meeting_minutes(2, 1, str(UUID(int=1)), "new-task")

    assert row.processing_task_id == "new-task"
    assert result["status"] == "ready"
    mock_start.assert_called_once_with(2)
    mock_loop.assert_called_once_with(2)
    mock_stop.assert_called_once_with(2)


@pytest.mark.unit
async def test_process_skips_live_worker():
    """A new worker must not take over a row with an active heartbeat."""
    row = MagicMock()
    row.id = 3
    row.status = MeetingMinutesStatus.PROCESSING
    row.processing_task_id = "old-task"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    with (
        patch(
            "app.tasks.process_meeting_minutes.get_celery_session_maker",
            return_value=lambda: MagicMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ),
        patch(
            "app.tasks.process_meeting_minutes.meeting_minutes_heartbeat_is_alive",
            return_value=True,
        ),
        patch(
            "app.tasks.process_meeting_minutes.MeetingMinutesService.process"
        ) as mock_process,
    ):
        result = await _process_meeting_minutes(3, 1, str(UUID(int=1)), "new-task")

    assert result["status"] == "processing"
    mock_process.assert_not_called()
