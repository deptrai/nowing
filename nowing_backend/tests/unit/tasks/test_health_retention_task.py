"""Unit tests for cleanup_admin_health_history Celery task."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.celery_tasks.health_retention_task import _cleanup_health_history


@pytest.mark.asyncio
async def test_cleanup_health_history_deletes_old_records() -> None:
    """The retention task should delete history records older than the retention window."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 42

    captured_stmt = None
    async def execute_side_effect(stmt):
        nonlocal captured_stmt
        captured_stmt = stmt
        return mock_result

    mock_session.execute = execute_side_effect
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    def _make_session():
        class _SessionCtx:
            async def __aenter__(self):
                return mock_session
            async def __aexit__(self, *args):
                return False
        return _SessionCtx()

    session_maker = MagicMock()
    session_maker.return_value = _make_session()

    with patch("app.tasks.celery_tasks.health_retention_task.get_celery_session_maker", return_value=session_maker):
        result = await _cleanup_health_history()

    assert result == {"deleted": 42, "retention_days": 30}
    assert captured_stmt is not None
