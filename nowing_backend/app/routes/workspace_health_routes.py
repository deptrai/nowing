"""REST endpoints for Workspace Health & Adoption Analytics (Story 29.2, AD-52)."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, get_async_session, has_permission
from app.schemas.workspace_health import (
    CoverageGapsResponse,
    SourceBreakdownResponse,
    WorkspaceHealthRange,
    WorkspaceHealthSummaryResponse,
)
from app.services.workspace_health_service import WorkspaceHealthService
from app.users import require_session_context
from app.utils.rbac import get_user_membership, get_user_permissions

router = APIRouter(prefix="/workspaces", tags=["workspace-health"])


async def _resolve_analytics_rbac(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> bool:
    """Check permissions and return whether public snapshot mode applies (INV-29.3).

    Returns:
        is_public_snapshot (bool): False if user has full access (Owner or ANALYTICS_READ),
        True if user has MEMORY_READ only.
    Raises:
        HTTPException(403) if user has neither.
    """
    membership = await get_user_membership(session, auth.user.id, workspace_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this workspace",
        )

    user_perms = await get_user_permissions(session, auth.user.id, workspace_id)
    has_analytics = (
        membership.is_owner
        or has_permission(user_perms, Permission.ANALYTICS_READ.value)
        or has_permission(user_perms, Permission.FULL_ACCESS.value)
    )
    has_memory = has_permission(user_perms, Permission.MEMORY_READ.value)

    if not has_analytics and not has_memory:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view workspace health analytics",
        )

    return not has_analytics


@router.get(
    "/{workspace_id}/health",
    response_model=WorkspaceHealthSummaryResponse,
)
async def get_workspace_health(
    workspace_id: int,
    date_range: WorkspaceHealthRange = Query(
        WorkspaceHealthRange.RANGE_30D,
        alias="range",
        description="Time range: 7d, 30d, 90d, or custom",
    ),
    start_date: date | None = Query(
        None, alias="start_date", description="Start date (YYYY-MM-DD) for custom date_range"
    ),
    end_date: date | None = Query(
        None, alias="end_date", description="End date (YYYY-MM-DD) for custom date_range"
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> WorkspaceHealthSummaryResponse:
    """Retrieve workspace health, adoption, sparklines, and quota analytics (AC-2)."""
    is_public_snapshot = await _resolve_analytics_rbac(session, auth, workspace_id)
    return await WorkspaceHealthService.get_health_summary(
        session=session,
        workspace_id=workspace_id,
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        is_public_snapshot=is_public_snapshot,
    )


@router.get(
    "/{workspace_id}/health/sources/{source_type}",
    response_model=SourceBreakdownResponse,
)
async def get_source_drilldown(
    workspace_id: int,
    source_type: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> SourceBreakdownResponse:
    """Retrieve source-level drilldown with volume, cost, and recent memory samples (AC-3)."""
    is_public_snapshot = await _resolve_analytics_rbac(session, auth, workspace_id)
    return await WorkspaceHealthService.get_source_drilldown(
        session=session,
        workspace_id=workspace_id,
        source_type=source_type,
        is_public_snapshot=is_public_snapshot,
    )


@router.get(
    "/{workspace_id}/health/coverage-gaps",
    response_model=CoverageGapsResponse,
)
async def get_coverage_gaps(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> CoverageGapsResponse:
    """Identify enabled knowledge/scraper sources with zero memories in trailing 30 days (AC-4)."""
    await _resolve_analytics_rbac(session, auth, workspace_id)
    return await WorkspaceHealthService.get_coverage_gaps(
        session=session,
        workspace_id=workspace_id,
    )


@router.get(
    "/{workspace_id}/health/export",
)
async def export_workspace_health(
    workspace_id: int,
    format: Literal["csv", "json"] = Query(
        "csv", description="Export format: csv or json"
    ),
    date_range: WorkspaceHealthRange = Query(
        WorkspaceHealthRange.RANGE_30D,
        alias="range",
        description="Time range: 7d, 30d, 90d, or custom",
    ),
    start_date: date | None = Query(
        None, alias="start_date", description="Start date (YYYY-MM-DD) for custom date_range"
    ),
    end_date: date | None = Query(
        None, alias="end_date", description="End date (YYYY-MM-DD) for custom date_range"
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> Response:
    """Export workspace health metrics as CSV or JSON (AC-6)."""
    is_public_snapshot = await _resolve_analytics_rbac(session, auth, workspace_id)
    summary = await WorkspaceHealthService.get_health_summary(
        session=session,
        workspace_id=workspace_id,
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        is_public_snapshot=is_public_snapshot,
    )

    filename_prefix = f"workspace_{workspace_id}_health_{summary.date_range}"

    if format == "json":
        json_content = summary.model_dump_json(indent=2)
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_prefix}.json"'
            },
        )

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "active_members_dau",
            "active_members_wau",
            "total_memories",
            "memory_growth_count",
            "recall_queries",
            "remember_queries",
            "research_queries",
            "query_volume",
            "credits_consumed_micros",
            "cost_per_turn_micros",
        ]
    )

    for p in summary.daily_metrics:
        writer.writerow(
            [
                p.date,
                "" if p.active_members_dau is None else p.active_members_dau,
                "" if p.active_members_wau is None else p.active_members_wau,
                p.total_memories,
                p.memory_growth_count,
                p.recall_queries,
                p.remember_queries,
                p.research_queries,
                p.query_volume,
                "" if p.credits_consumed_micros is None else p.credits_consumed_micros,
                "" if p.cost_per_turn_micros is None else p.cost_per_turn_micros,
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_prefix}.csv"'
        },
    )
