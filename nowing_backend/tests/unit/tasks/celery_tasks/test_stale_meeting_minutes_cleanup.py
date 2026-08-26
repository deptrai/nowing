"""Unit tests for the meeting-minutes stale-job reaper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db import MeetingMinutesStatus
from app.tasks.celery_tasks.stale_meeting_minutes_cleanup_task import (
    _cleanup_stale_meeting_minutes,
)


@pytest.mark.unit
async def test_cleanup_marks_processing_rows_without_heartbeat_as_failed():
    """Rows in PROCESSING with missing heartbeat are marked FAILED."""
    redis_client = MagicMock()
    redis_client.exists = MagicMock(return_value=0)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [7, 8]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    with (
        patch(
            "app.tasks.celery_tasks.stale_meeting_minutes_cleanup_task.get_redis_client",
            return_value=redis_client,
        ),
        patch(
            "app.tasks.celery_tasks.stale_meeting_minutes_cleanup_task.get_celery_session_maker",
            return_value=lambda: MagicMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ),
    ):
        await _cleanup_stale_meeting_minutes()

    # SELECT then UPDATE.
    assert session.execute.call_count == 2
    update_stmt = session.execute.call_args_list[1].args[0]
    # SQLAlchemy Update._values is an immutabledict of column -> BindParameter.
    columns = {col.key: value.value for col, value in update_stmt._values.items()}
    assert columns["status"] == MeetingMinutesStatus.FAILED.value
    assert columns["error"] == "processing_task_interrupted"
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_cleanup_skips_rows_with_active_heartbeat():
    """Rows with an existing heartbeat are left alone."""
    redis_client = MagicMock()
    redis_client.exists = MagicMock(return_value=1)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [9]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    with (
        patch(
            "app.tasks.celery_tasks.stale_meeting_minutes_cleanup_task.get_redis_client",
            return_value=redis_client,
        ),
        patch(
            "app.tasks.celery_tasks.stale_meeting_minutes_cleanup_task.get_celery_session_maker",
            return_value=lambda: MagicMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ),
    ):
        await _cleanup_stale_meeting_minutes()

    # Only the SELECT ran; no UPDATE.
    assert session.execute.call_count == 1
    session.commit.assert_not_awaited()


@pytest.mark.unit
async def test_cleanup_aborts_when_redis_is_unreachable():
    """If Redis is down the reaper must not mark rows as failed."""
    with (
        patch(
            "app.tasks.celery_tasks.stale_meeting_minutes_cleanup_task.get_redis_client",
            side_effect=RuntimeError("redis down"),
        ),
        patch(
            "app.tasks.celery_tasks.stale_meeting_minutes_cleanup_task.get_celery_session_maker"
        ) as mock_session_maker,
    ):
        await _cleanup_stale_meeting_minutes()

    mock_session_maker.assert_not_called()
