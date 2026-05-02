"""Unit tests for crypto_refresh_tasks — AC1 through AC4."""
import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot_row(project_id=1, data_category="defi_tvl", tool_name="get_defillama_protocol", tool_args=None):
    row = MagicMock()
    row.project_id = project_id
    row.data_category = data_category
    row.tool_name = tool_name
    row.tool_args = tool_args or {"protocol_slug": "uniswap"}
    return row


class _FakeSession:
    def __init__(self, execute_return=None):
        self._execute_return = execute_return or MagicMock(fetchall=lambda: [])
        self.committed = False

    async def execute(self, *a, **kw):
        return self._execute_return

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


def _make_session_maker(session):
    def _maker():
        return session
    return _maker


# ---------------------------------------------------------------------------
# AC1: Refresh task finds expiring snapshots and prefetches them
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac1_refresh_finds_expiring_snapshots_and_prefetches():
    """_async_refresh_popular calls _prefetch_category for each expiring row."""
    rows = [_make_snapshot_row()]
    fetch_result = MagicMock()
    fetch_result.fetchall.return_value = rows
    session = _FakeSession(execute_return=fetch_result)

    prefetched = []

    async def _fake_prefetch(project_id, category, tool_name, tool_args, tool_fn_map):
        prefetched.append((project_id, category, tool_name))

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ), patch(
        "app.agents.new_chat.tools.registry.BUILTIN_TOOLS",
        [],
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._prefetch_category",
        side_effect=_fake_prefetch,
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_refresh_popular
        await _async_refresh_popular()

    assert len(prefetched) == 1
    assert prefetched[0] == (1, "defi_tvl", "get_defillama_protocol")


# ---------------------------------------------------------------------------
# AC2: Rate limit handling — skip, don't crash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac2_prefetch_error_skipped_task_continues():
    """If one _prefetch_category raises, the task logs and continues to next row."""
    rows = [
        _make_snapshot_row(project_id=1, tool_name="get_defillama_protocol"),
        _make_snapshot_row(project_id=2, tool_name="get_coingecko_token_info"),
    ]
    fetch_result = MagicMock()
    fetch_result.fetchall.return_value = rows
    session = _FakeSession(execute_return=fetch_result)

    call_order = []

    async def _failing_then_ok(project_id, category, tool_name, tool_args, tool_fn_map):
        call_order.append(project_id)
        if project_id == 1:
            raise RuntimeError("429 rate limited")

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ), patch(
        "app.agents.new_chat.tools.registry.BUILTIN_TOOLS",
        [],
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._prefetch_category",
        side_effect=_failing_then_ok,
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_refresh_popular
        # Should NOT raise even though first prefetch fails
        await _async_refresh_popular()

    assert call_order == [1, 2], "Both rows must be attempted despite first failure"


# ---------------------------------------------------------------------------
# AC3: Cleanup — 30-day retention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac3_cleanup_deletes_old_snapshots():
    """_async_cleanup issues DELETE for rows older than 30 days."""
    delete_result = MagicMock()
    delete_result.rowcount = 5

    executed_stmts = []

    class _TrackingSession:
        committed = False

        async def execute(self, stmt, *a, **kw):
            executed_stmts.append(stmt)
            return delete_result

        async def commit(self):
            self.committed = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    session = _TrackingSession()

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._prune_per_category",
        new=AsyncMock(),
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup
        await _async_cleanup()

    # Two DELETEs must have been issued (30d and 24h)
    assert len(executed_stmts) == 2, f"Expected 2 DELETE statements, got {len(executed_stmts)}"
    assert session.committed


# ---------------------------------------------------------------------------
# AC4: Cleanup — error snapshot 24h retention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac4_cleanup_deletes_error_snapshots_24h():
    """_async_cleanup issues a separate DELETE for is_error=True rows older than 24h."""
    delete_result = MagicMock()
    delete_result.rowcount = 3

    executed_clauses = []

    class _TrackingSession:
        committed = False

        async def execute(self, stmt, *a, **kw):
            executed_clauses.append(str(stmt))
            return delete_result

        async def commit(self):
            self.committed = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    session = _TrackingSession()

    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks.get_celery_session_maker",
        return_value=_make_session_maker(session),
    ), patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._prune_per_category",
        new=AsyncMock(),
    ):
        from app.tasks.celery_tasks.crypto_refresh_tasks import _async_cleanup
        await _async_cleanup()

    # Verify at least one DELETE clause references is_error
    combined = " ".join(executed_clauses)
    assert "is_error" in combined.lower(), "Expected a DELETE targeting is_error snapshots"


# ---------------------------------------------------------------------------
# AC5: Beat schedule names registered
# ---------------------------------------------------------------------------


def test_ac5_beat_schedule_registered():
    """Both crypto tasks appear in celery_app beat_schedule."""
    from celery.schedules import crontab

    from app.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "crypto-refresh-popular-data" in schedule, (
        "crypto-refresh-popular-data not in beat_schedule"
    )
    assert "crypto-cleanup-expired-snapshots" in schedule, (
        "crypto-cleanup-expired-snapshots not in beat_schedule"
    )

    refresh_entry = schedule["crypto-refresh-popular-data"]
    assert refresh_entry["task"] == "crypto.refresh_popular_data"
    assert refresh_entry["schedule"] == crontab(minute="*/30")

    cleanup_entry = schedule["crypto-cleanup-expired-snapshots"]
    assert cleanup_entry["task"] == "crypto.cleanup_expired_snapshots"
    assert cleanup_entry["schedule"] == crontab(hour=3, minute=0)


# ---------------------------------------------------------------------------
# Extra: cache disabled flag → refresh skips
# ---------------------------------------------------------------------------


def test_refresh_skips_when_cache_disabled():
    """refresh_popular_crypto_data exits early if _CACHE_ENABLED=False."""
    with patch(
        "app.tasks.celery_tasks.crypto_refresh_tasks._CACHE_ENABLED", False, create=True
    ):
        import importlib
        from app.tasks.celery_tasks import crypto_refresh_tasks
        importlib.reload(crypto_refresh_tasks)

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache._CACHE_ENABLED", False
    ), patch(
        "asyncio.new_event_loop"
    ) as mock_loop:
        from app.tasks.celery_tasks.crypto_refresh_tasks import refresh_popular_crypto_data
        refresh_popular_crypto_data()
        mock_loop.assert_not_called()
