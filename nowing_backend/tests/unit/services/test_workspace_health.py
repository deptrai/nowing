"""Unit tests for WorkspaceHealthService (Story 29.2, Task 5.1)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.workspace_health import (
    MetricCardSummary,
    QuotaProgressItem,
    WorkspaceHealthRange,
    WorkspaceHealthSummaryResponse,
)
from app.services.workspace_health_service import (
    PLAN_DEFAULT_MONTHLY_CREDITS,
    TIER_PROGRESSION,
    WorkspaceHealthService,
)

pytestmark = pytest.mark.unit


class MockLimits:
    def __init__(
        self,
        plan_tier: str = "free",
        max_memory_count: int | None = 1000,
        max_storage_bytes: int | None = 100_000_000,
        max_monthly_credits: int | None = 500_000,
    ):
        self.plan_tier = plan_tier
        self.max_memory_count = max_memory_count
        self.max_storage_bytes = max_storage_bytes
        self.max_monthly_credits = max_monthly_credits


@pytest.mark.asyncio
async def test_quota_progress_normal_state():
    """Test quota progress calculation when utilization is under 80%."""
    session = AsyncMock()

    mock_limits = MockLimits(
        plan_tier="team",
        max_memory_count=10_000,
        max_storage_bytes=500_000_000,
        max_monthly_credits=5_000_000,
    )

    with (
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
            return_value=mock_limits,
        ),
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.count_memories",
            return_value=2_000,
        ),
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.sum_storage_bytes",
            return_value=100_000_000,
        ),
    ):
        mock_credits_result = MagicMock()
        mock_credits_result.scalar.return_value = 1_000_000
        session.execute.return_value = mock_credits_result

        items = await WorkspaceHealthService._get_quota_progress(session, workspace_id=1)

        assert len(items) == 3
        # Memory item
        mem_item = next(i for i in items if i.metric == "memory_count")
        assert mem_item.current_value == 2_000
        assert mem_item.limit_value == 10_000
        assert mem_item.utilization_pct == 20.0
        assert mem_item.status == "normal"
        assert mem_item.recommended_tier is None

        # Credits item
        cred_item = next(i for i in items if i.metric == "monthly_credits")
        assert cred_item.current_value == 1_000_000
        assert cred_item.limit_value == 5_000_000
        assert cred_item.utilization_pct == 20.0
        assert cred_item.status == "normal"


@pytest.mark.asyncio
async def test_quota_progress_warning_threshold_and_tier_recommendation():
    """Test quota progress at >=80% triggers warning status and suggests next tier."""
    session = AsyncMock()

    mock_limits = MockLimits(
        plan_tier="free",
        max_memory_count=1_000,
        max_storage_bytes=100_000_000,
        max_monthly_credits=500_000,
    )

    with (
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
            return_value=mock_limits,
        ),
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.count_memories",
            return_value=850,  # 85% utilization
        ),
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.sum_storage_bytes",
            return_value=10_000_000,
        ),
    ):
        mock_credits_result = MagicMock()
        mock_credits_result.scalar.return_value = 100_000
        session.execute.return_value = mock_credits_result

        items = await WorkspaceHealthService._get_quota_progress(session, workspace_id=1)
        mem_item = next(i for i in items if i.metric == "memory_count")

        assert mem_item.utilization_pct == 85.0
        assert mem_item.status == "warning"
        assert mem_item.recommended_tier == "Team"


@pytest.mark.asyncio
async def test_quota_progress_alert_threshold():
    """Test quota progress at >=100% triggers alert status."""
    session = AsyncMock()

    mock_limits = MockLimits(
        plan_tier="growth",
        max_memory_count=50_000,
        max_storage_bytes=1_000_000_000,
        max_monthly_credits=25_000_000,
    )

    with (
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
            return_value=mock_limits,
        ),
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.count_memories",
            return_value=55_000,  # 110% utilization
        ),
        patch(
            "app.services.workspace_limits.WorkspaceLimitService.sum_storage_bytes",
            return_value=10_000_000,
        ),
    ):
        mock_credits_result = MagicMock()
        mock_credits_result.scalar.return_value = 100_000
        session.execute.return_value = mock_credits_result

        items = await WorkspaceHealthService._get_quota_progress(session, workspace_id=1)
        mem_item = next(i for i in items if i.metric == "memory_count")

        assert mem_item.utilization_pct == 110.0
        assert mem_item.status == "alert"
        assert mem_item.recommended_tier == "Enterprise"


@pytest.mark.asyncio
async def test_public_snapshot_masking():
    """Test that is_public_snapshot=True strictly masks financial and identity metrics to None."""
    session = AsyncMock()

    # Mock DB queries for get_health_summary
    mock_history_res = MagicMock()
    mock_history_res.scalars.return_value.all.return_value = []

    mock_live_today = MagicMock()
    mock_live_today.active_members_dau = 5
    mock_live_today.active_members_wau = 12
    mock_live_today.total_memories = 150
    mock_live_today.memory_growth_count = 10
    mock_live_today.recall_queries = 20
    mock_live_today.remember_queries = 5
    mock_live_today.research_queries = 15
    mock_live_today.query_volume = 40
    mock_live_today.credits_consumed_micros = 120_000
    mock_live_today.cost_per_turn_micros = 3_000

    with (
        patch("app.services.workspace_health_service.set_request_tenant_context", new_callable=AsyncMock),
        patch.object(
            WorkspaceHealthService,
            "_rollup_for_workspace_date",
            new_callable=AsyncMock,
            return_value=mock_live_today,
        ),
        patch.object(
            WorkspaceHealthService,
            "_count_coverage_gaps",
            new_callable=AsyncMock,
            return_value=0,
        ),
    ):
        # Setup session.execute return values for queries in get_health_summary
        mock_empty_res = MagicMock()
        mock_empty_res.scalars.return_value.all.return_value = []
        mock_empty_res.all.return_value = []

        session.execute.return_value = mock_empty_res

        summary = await WorkspaceHealthService.get_health_summary(
            session=session,
            workspace_id=1,
            date_range=WorkspaceHealthRange.RANGE_7D,
            is_public_snapshot=True,
        )

        assert summary.is_public_snapshot is True
        # Masked fields
        assert summary.active_members_dau is None
        assert summary.active_members_wau is None
        assert summary.credits_consumed_micros is None
        assert summary.cost_per_turn_micros is None
        assert summary.quota_progress is None

        # Unmasked fields
        assert summary.total_memories is not None
        assert summary.memory_growth_count is not None
        assert summary.query_volume is not None


@pytest.mark.asyncio
async def test_source_drilldown_nonexistent_source_raises_404():
    """Test that querying a source type with 0 memories and no connector raises 404."""
    session = AsyncMock()

    with patch("app.services.workspace_health_service.set_request_tenant_context", new_callable=AsyncMock):
        # 1. memories count query -> 0
        mem_count_res = MagicMock()
        mem_count_res.scalar.return_value = 0

        # 2. connectors count query -> 0
        conn_count_res = MagicMock()
        conn_count_res.scalar.return_value = 0

        session.execute.side_effect = [mem_count_res, conn_count_res]

        with pytest.raises(HTTPException) as exc_info:
            await WorkspaceHealthService.get_source_drilldown(
                session=session,
                workspace_id=1,
                source_type="nonexistent_source",
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_get_coverage_gaps_flags_inactive_connectors():
    """Test that enabled connectors with 0 memories in 30 days are reported as gaps."""
    session = AsyncMock()

    mock_conn = MagicMock()
    mock_conn.connector_type = "google_drive"
    mock_conn.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    mock_conn.last_indexed_at = None

    with patch("app.services.workspace_health_service.set_request_tenant_context", new_callable=AsyncMock):
        # 1. Connectors list
        conn_list_res = MagicMock()
        conn_list_res.scalars.return_value.all.return_value = [mock_conn]

        # 2. Memories count for google_drive -> 0
        mem_count_res = MagicMock()
        mem_count_res.scalar.return_value = 0

        session.execute.side_effect = [conn_list_res, mem_count_res]

        gaps_response = await WorkspaceHealthService.get_coverage_gaps(session, workspace_id=1)

        assert gaps_response.total_gaps == 1
        assert len(gaps_response.gaps) == 1
        gap = gaps_response.gaps[0]
        assert gap.source_type == "google_drive"
        assert "credentials" in gap.remediation_action.lower() or "sync" in gap.remediation_action.lower()
        assert gap.configure_url == "/dashboard/1/connectors"

