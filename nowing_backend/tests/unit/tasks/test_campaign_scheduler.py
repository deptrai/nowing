"""Unit tests Epic 44.3 — ``check_campaign_schedules`` meta-scheduler.

Cover: tick due launch (trigger 'scheduled' + apply_async sau commit),
skip khi quota/concurrent (``skipped_by_quota`` +1, không run row), max_runs
→ 'completed', stale-run reaper → failed 'stale_run_timeout', per-workspace
tenant GUC. Mock session — phân biệt statement theo tên bảng trong SQL.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.lead_intelligence.services.campaign_service import (
    CampaignQuotaExceededError,
    ConcurrentCampaignRunError,
)
from app.tasks.campaign_tasks import check_campaign_schedules

pytestmark = pytest.mark.unit


class _Result:
    """Fake SQLAlchemy result — scalars().all() hoặc scalar_one()."""

    def __init__(self, scalars: list[Any] | None = None, scalar: Any = None):
        self._scalars = scalars if scalars is not None else []
        self._scalar = scalar

    def scalars(self) -> Any:
        outer = self

        class _Scalars:
            def all(self) -> list[Any]:
                return list(outer._scalars)

        return _Scalars()

    def scalar_one(self) -> Any:
        return self._scalar


class _TaskSession:
    """Fake AsyncSession — định tuyến execute() theo tên bảng trong SQL."""

    def __init__(
        self,
        workspaces: list[int] | None = None,
        stale: list[Any] | None = None,
        due: list[Any] | None = None,
        runs_counts: list[int] | None = None,
    ) -> None:
        self._workspaces = workspaces if workspaces is not None else []
        self._stale = stale if stale is not None else []
        self._due = due if due is not None else []
        self._runs_counts = list(runs_counts or [])
        self.commits = 0
        self.statements: list[str] = []

    async def execute(self, stmt: Any, params: Any = None) -> _Result:
        sql = str(stmt)
        self.statements.append(sql)
        if "FROM workspaces" in sql:
            return _Result(scalars=self._workspaces)
        if "FROM campaign_runs" in sql:
            if "count(" in sql:
                return _Result(
                    scalar=(
                        self._runs_counts.pop(0)
                        if self._runs_counts
                        else 0
                    )
                )
            return _Result(scalars=self._stale)
        if "FROM lead_campaigns" in sql:
            return _Result(scalars=self._due)
        return _Result()

    async def commit(self) -> None:
        self.commits += 1


class _SessionCM:
    def __init__(self, session: _TaskSession) -> None:
        self._session = session

    async def __aenter__(self) -> _TaskSession:
        return self._session

    async def __aexit__(self, *exc: Any) -> bool:
        return False


def _run_coro(factory: Any) -> Any:
    return asyncio.run(factory())


def _due_campaign(**kwargs: Any) -> SimpleNamespace:
    """Campaign scheduled + next_run_at quá khứ."""
    campaign = SimpleNamespace(
        id=uuid4(),
        workspace_id=10,
        status="scheduled",
        next_run_at=datetime.now(UTC) - timedelta(minutes=5),
        schedule_frequency="daily",
        schedule_cron=None,
        max_runs=None,
        skipped_by_quota=0,
        input_payload={"name": "C"},
    )
    for key, value in kwargs.items():
        setattr(campaign, key, value)
    return campaign


def _patch_task(
    session: _TaskSession,
    open_run: Any = None,
    finalize: Any = None,
) -> tuple[Any, ...]:
    return (
        patch(
            "app.tasks.campaign_tasks.async_session_maker",
            return_value=_SessionCM(session),
        ),
        patch(
            "app.tasks.campaign_tasks.set_request_tenant_context",
            AsyncMock(),
        ),
        patch(
            "app.tasks.campaign_tasks.run_async_celery_task", _run_coro
        ),
        patch(
            "app.tasks.campaign_tasks.campaign_service.open_campaign_run",
            open_run if open_run is not None else AsyncMock(),
        ),
        patch(
            "app.tasks.campaign_tasks.campaign_service.finalize_campaign_run",
            finalize if finalize is not None else AsyncMock(),
        ),
        patch(
            "app.tasks.campaign_tasks.launch_campaign_run"
        ) ,
    )


def test_tick_launches_due_campaign() -> None:
    """Due campaign → open run 'scheduled' → commit → apply_async; next_run_at
    được recompute sang tương lai."""
    campaign = _due_campaign()
    run = SimpleNamespace(id=uuid4(), status="running")
    open_run = AsyncMock(return_value=run)
    session = _TaskSession(workspaces=[10], due=[campaign], runs_counts=[2])

    p_maker, p_ctx, p_runner, p_open, p_fin, p_launch = _patch_task(
        session, open_run=open_run
    )
    with p_maker, p_ctx as tenant_ctx, p_runner, p_open as open_mock, p_fin, p_launch as launch_mock:
        result = check_campaign_schedules.run()

    assert result["launched"] == 1
    assert result["skipped"] == 0
    open_mock.assert_awaited_once()
    args, kwargs = open_mock.call_args
    assert args[0] == campaign.id
    assert args[1] == "scheduled"
    launch_mock.apply_async.assert_called_once_with(
        args=[str(campaign.id), str(run.id), 10]
    )
    # Tenant GUC phải set trước khi scan (RLS).
    tenant_ctx.assert_awaited()
    tenant_ctx.assert_any_await(session, workspace_id=10)
    # commit trước apply_async: commits>=1 và next_run_at đã sang tương lai.
    assert session.commits >= 1
    assert campaign.next_run_at > datetime.now(UTC)


def test_tick_not_due_does_nothing() -> None:
    """Không có campaign due → không open, không launch."""
    session = _TaskSession(workspaces=[10], due=[])
    p_maker, p_ctx, p_runner, p_open, p_fin, p_launch = _patch_task(session)
    with p_maker, p_ctx, p_runner, p_open as open_mock, p_fin, p_launch as launch_mock:
        result = check_campaign_schedules.run()

    assert result["launched"] == 0
    open_mock.assert_not_awaited()
    launch_mock.apply_async.assert_not_called()


def test_tick_quota_skip_increments_counter() -> None:
    """open_campaign_run raise CampaignQuotaExceededError → skip +
    skipped_by_quota += 1, không launch."""
    campaign = _due_campaign()
    open_run = AsyncMock(
        side_effect=CampaignQuotaExceededError(
            "quota", campaign_id=campaign.id, reason="runs_per_day"
        )
    )
    session = _TaskSession(workspaces=[10], due=[campaign], runs_counts=[9])

    p_maker, p_ctx, p_runner, p_open, p_fin, p_launch = _patch_task(
        session, open_run=open_run
    )
    with p_maker, p_ctx, p_runner, p_open, p_fin, p_launch as launch_mock:
        result = check_campaign_schedules.run()

    assert result["skipped"] == 1
    assert result["launched"] == 0
    assert campaign.skipped_by_quota == 1
    assert campaign.status == "scheduled"
    launch_mock.apply_async.assert_not_called()
    # next_run_at vẫn recompute để không lặp skip mỗi phút mãi.
    assert campaign.next_run_at > datetime.now(UTC)


def test_tick_concurrent_skip_increments_counter() -> None:
    """Run trước còn 'running' → ConcurrentCampaignRunError → skip + counter."""
    campaign = _due_campaign()
    open_run = AsyncMock(
        side_effect=ConcurrentCampaignRunError(campaign.id, uuid4())
    )
    session = _TaskSession(workspaces=[10], due=[campaign], runs_counts=[1])

    p_maker, p_ctx, p_runner, p_open, p_fin, p_launch = _patch_task(
        session, open_run=open_run
    )
    with p_maker, p_ctx, p_runner, p_open, p_fin, p_launch as launch_mock:
        result = check_campaign_schedules.run()

    assert result["skipped"] == 1
    assert campaign.skipped_by_quota == 1
    launch_mock.apply_async.assert_not_called()


def test_max_runs_marks_completed() -> None:
    """runs_count >= max_runs → status 'completed', next_run_at None, không open."""
    campaign = _due_campaign(max_runs=3)
    open_run = AsyncMock()
    session = _TaskSession(workspaces=[10], due=[campaign], runs_counts=[3])

    p_maker, p_ctx, p_runner, p_open, p_fin, p_launch = _patch_task(
        session, open_run=open_run
    )
    with p_maker, p_ctx, p_runner, p_open, p_fin, p_launch:
        result = check_campaign_schedules.run()

    assert result["completed"] == 1
    assert result["launched"] == 0
    assert campaign.status == "completed"
    assert campaign.next_run_at is None
    open_run.assert_not_awaited()


def test_stale_run_reaped_failed() -> None:
    """Run 'running' quá 2h → finalize 'failed' với 'stale_run_timeout'."""
    stale_run = SimpleNamespace(
        id=uuid4(),
        status="running",
        workspace_id=10,
        started_at=datetime.now(UTC) - timedelta(hours=3),
    )
    finalize = AsyncMock()
    session = _TaskSession(workspaces=[10], stale=[stale_run])

    p_maker, p_ctx, p_runner, p_open, p_fin, p_launch = _patch_task(
        session, finalize=finalize
    )
    with p_maker, p_ctx, p_runner, p_open, p_fin, p_launch:
        result = check_campaign_schedules.run()

    assert result["reaped"] == 1
    finalize.assert_awaited_once()
    _args, kwargs = finalize.call_args
    assert kwargs["run_id"] == stale_run.id
    assert kwargs["status"] == "failed"
    assert kwargs["error"] == "stale_run_timeout"
    assert session.commits >= 1


def test_multi_workspace_tenant_context_per_workspace() -> None:
    """Mỗi workspace được set tenant GUC riêng trước khi scan."""
    session = _TaskSession(workspaces=[10, 20])
    p_maker, p_ctx, p_runner, p_open, p_fin, p_launch = _patch_task(session)
    with p_maker, p_ctx as tenant_ctx, p_runner, p_open, p_fin, p_launch:
        check_campaign_schedules.run()

    calls = [c.kwargs["workspace_id"] for c in tenant_ctx.await_args_list]
    assert calls == [10, 20]
