"""Unit tests cho quota guard + ``compute_next_run_at`` (Epic 44.3).

AsyncMock session — không DB thật. Cover: runs/day quota, workspace leads/day
quota, ordering lock → concurrent → quota → insert, next_run_at compute
(hourly/daily/weekly/monthly/cron/max_runs/no-schedule).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.lead_intelligence.services.campaign_service import (
    CAMPAIGN_MAX_RUNS_PER_DAY,
    WORKSPACE_MAX_CAMPAIGN_LEADS_PER_DAY,
    CampaignQuotaExceededError,
    ConcurrentCampaignRunError,
    compute_next_run_at,
    open_campaign_run,
)

pytestmark = pytest.mark.unit


def _campaign(workspace_id: int = 10, status: str = "scheduled") -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.workspace_id = workspace_id
    c.status = status
    return c


def _lock_result() -> MagicMock:
    return MagicMock()


def _running_result(run_id: uuid.UUID | None) -> MagicMock:
    res = MagicMock()
    res.first.return_value = (run_id,) if run_id else None
    return res


def _count_result(n: int) -> MagicMock:
    res = MagicMock()
    res.scalar_one.return_value = n
    return res


def _session(
    campaign: MagicMock | None, *results: MagicMock
) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=campaign)
    session.execute = AsyncMock(side_effect=list(results))
    # session.add là sync API — MagicMock thường để tránh unawaited coroutine.
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Quota: runs/ngày của campaign
# ---------------------------------------------------------------------------


class TestRunsPerDayQuota:
    @pytest.mark.asyncio
    async def test_at_limit_raises_no_insert(self) -> None:
        """Đủ CAMPAIGN_MAX_RUNS_PER_DAY run hôm nay → raise, không add run."""
        campaign = _campaign()
        session = _session(
            campaign,
            _lock_result(),
            _running_result(None),
            _count_result(CAMPAIGN_MAX_RUNS_PER_DAY),
        )
        with pytest.raises(CampaignQuotaExceededError) as exc_info:
            await open_campaign_run(campaign.id, "manual", session)
        assert exc_info.value.reason == "runs_per_day"
        assert exc_info.value.campaign_id == campaign.id
        session.add.assert_not_called()
        # Campaign status KHÔNG bị mutate sang 'running' khi quota chặn.
        assert campaign.status == "scheduled"

    @pytest.mark.asyncio
    async def test_over_limit_raises(self) -> None:
        campaign = _campaign()
        session = _session(
            campaign,
            _lock_result(),
            _running_result(None),
            _count_result(CAMPAIGN_MAX_RUNS_PER_DAY + 3),
        )
        with pytest.raises(CampaignQuotaExceededError):
            await open_campaign_run(campaign.id, "api", session)
        session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Quota: leads/ngày workspace-wide
# ---------------------------------------------------------------------------


class TestWorkspaceLeadsPerDayQuota:
    @pytest.mark.asyncio
    async def test_at_limit_raises(self) -> None:
        campaign = _campaign(workspace_id=42)
        session = _session(
            campaign,
            _lock_result(),
            _running_result(None),
            _count_result(0),  # runs today OK
            _count_result(WORKSPACE_MAX_CAMPAIGN_LEADS_PER_DAY),
        )
        with pytest.raises(CampaignQuotaExceededError) as exc_info:
            await open_campaign_run(campaign.id, "scheduled", session)
        assert exc_info.value.reason == "workspace_leads_per_day"
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_runs_quota_checked_before_leads(self) -> None:
        """Runs quota chặn trước → leads query không cần chạy tới."""
        campaign = _campaign()
        session = _session(
            campaign,
            _lock_result(),
            _running_result(None),
            _count_result(CAMPAIGN_MAX_RUNS_PER_DAY),
            # không cung cấp result thứ 4 — nếu leads query chạy sẽ StopAsyncIteration
        )
        with pytest.raises(CampaignQuotaExceededError) as exc_info:
            await open_campaign_run(campaign.id, "manual", session)
        assert exc_info.value.reason == "runs_per_day"
        assert session.execute.await_count == 3


# ---------------------------------------------------------------------------
# Ordering + happy path
# ---------------------------------------------------------------------------


class TestQuotaOrdering:
    @pytest.mark.asyncio
    async def test_concurrent_check_trước_quota(self) -> None:
        """Run 'running' tồn tại → ConcurrentCampaignRunError (409), quota
        queries không chạy."""
        campaign = _campaign()
        session = _session(
            campaign,
            _lock_result(),
            _running_result(uuid.uuid4()),
        )
        with pytest.raises(ConcurrentCampaignRunError):
            await open_campaign_run(campaign.id, "manual", session)
        # lock + running-select; quota counts không được gọi.
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_under_quota_inserts_run(self) -> None:
        """Dưới cả 2 ngưỡng → run được insert, campaign → 'running'."""
        campaign = _campaign()
        session = _session(
            campaign,
            _lock_result(),
            _running_result(None),
            _count_result(3),
            _count_result(100),
        )
        run = await open_campaign_run(campaign.id, "scheduled", session)
        assert run.campaign_id == campaign.id
        assert run.trigger == "scheduled"
        assert run.status == "running"
        assert campaign.status == "running"
        session.add.assert_called_once_with(run)
        session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# compute_next_run_at
# ---------------------------------------------------------------------------


def _scheduled_campaign(**kwargs: object) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.max_runs = None
    c.schedule_cron = None
    c.schedule_frequency = "daily"
    for key, value in kwargs.items():
        setattr(c, key, value)
    return c


class TestComputeNextRunAt:
    def setup_method(self) -> None:
        self.now = datetime(2026, 11, 18, 10, 30, 0, tzinfo=UTC)

    def test_hourly(self) -> None:
        c = _scheduled_campaign(schedule_frequency="hourly")
        assert compute_next_run_at(c, now=self.now) == self.now + timedelta(
            hours=1
        )

    def test_daily(self) -> None:
        c = _scheduled_campaign(schedule_frequency="daily")
        assert compute_next_run_at(c, now=self.now) == self.now + timedelta(
            days=1
        )

    def test_weekly(self) -> None:
        c = _scheduled_campaign(schedule_frequency="weekly")
        assert compute_next_run_at(c, now=self.now) == self.now + timedelta(
            weeks=1
        )

    def test_monthly_keeps_day(self) -> None:
        c = _scheduled_campaign(schedule_frequency="monthly")
        nxt = compute_next_run_at(c, now=self.now)
        assert nxt is not None
        assert nxt.month == 12
        assert nxt.day == 18

    def test_cron_expression(self) -> None:
        c = _scheduled_campaign(
            schedule_frequency=None, schedule_cron="*/30 * * * *"
        )
        nxt = compute_next_run_at(c, now=self.now)
        # 10:30 → next */30 fire là 11:00.
        assert nxt == datetime(2026, 11, 18, 11, 0, 0, tzinfo=UTC)

    def test_cron_invalid_returns_none(self) -> None:
        c = _scheduled_campaign(
            schedule_frequency="daily", schedule_cron="not a cron"
        )
        assert compute_next_run_at(c, now=self.now) is None

    def test_once_no_recurrence(self) -> None:
        c = _scheduled_campaign(schedule_frequency="once")
        assert compute_next_run_at(c, now=self.now) is None

    def test_no_schedule_returns_none(self) -> None:
        c = _scheduled_campaign(schedule_frequency=None)
        assert compute_next_run_at(c, now=self.now) is None

    def test_max_runs_reached_returns_none(self) -> None:
        c = _scheduled_campaign(schedule_frequency="daily", max_runs=5)
        assert compute_next_run_at(c, runs_count=5, now=self.now) is None

    def test_max_runs_not_reached(self) -> None:
        c = _scheduled_campaign(schedule_frequency="daily", max_runs=5)
        assert compute_next_run_at(
            c, runs_count=4, now=self.now
        ) == self.now + timedelta(days=1)
