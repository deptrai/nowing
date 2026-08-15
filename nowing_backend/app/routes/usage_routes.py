from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.usage import (
    UsageSummaryResponse,
    UsageTimeSeriesResponse,
    UsageTransactionsResponse,
)
from app.services.usage_service import UsageService
from app.users import require_session_context
from app.utils.rbac import check_workspace_access

router = APIRouter(prefix="/usage", tags=["usage"])


def _validate_date_range(
    start_date: datetime | None, end_date: datetime | None
) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must not be after end_date",
        )


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    workspace_id: int = Query(..., ge=1),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
) -> UsageSummaryResponse:
    """Return a workspace usage/credit summary with usage breakdowns."""
    await check_workspace_access(session, auth, workspace_id)
    _validate_date_range(start_date, end_date)
    service = UsageService(session, auth.user)
    return await service.get_summary(workspace_id, start_date, end_date)


@router.get("/time-series", response_model=UsageTimeSeriesResponse)
async def get_usage_time_series(
    workspace_id: int = Query(..., ge=1),
    granularity: Literal["day", "week", "month"] = Query("day"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
) -> UsageTimeSeriesResponse:
    """Return time-series cost and token totals for a workspace."""
    await check_workspace_access(session, auth, workspace_id)
    _validate_date_range(start_date, end_date)
    service = UsageService(session, auth.user)
    return await service.get_time_series(
        workspace_id, granularity, start_date, end_date
    )


@router.get("/transactions", response_model=UsageTransactionsResponse)
async def get_usage_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
) -> UsageTransactionsResponse:
    """Return the authenticated user's unified credit transaction history."""
    service = UsageService(session, auth.user)
    return await service.get_transactions(limit, offset)


@router.get("/service-breakdown")
async def get_service_breakdown(
    workspace_id: int = Query(..., ge=1),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
):
    """Return usage breakdown categorized into 5 standardized service buckets."""
    await check_workspace_access(session, auth, workspace_id)
    _validate_date_range(start_date, end_date)
    service = UsageService(session, auth.user)
    norm_start, norm_end = service._normalize_range(start_date, end_date)
    items = await service.get_service_breakdown(workspace_id, norm_start, norm_end)
    return {
        "workspace_id": workspace_id,
        "start_date": norm_start,
        "end_date": norm_end,
        "items": items,
    }
