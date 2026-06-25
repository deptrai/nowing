from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    CryptoDataSnapshot,
    CryptoProject,
    SearchSpaceCryptoWatchlist,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.users import current_active_user
from app.utils.rbac import check_search_space_access

router = APIRouter()


class CryptoProjectResponse(BaseModel):
    id: int
    project_id: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    coingecko_id: Optional[str] = None
    defillama_slug: Optional[str] = None
    added_at: datetime
    pin_order: Optional[int] = None

    model_config = {"from_attributes": True}


class SnapshotResponse(BaseModel):
    id: int
    data_category: str
    tool_name: str
    api_source: str
    fetched_at: datetime
    expires_at: datetime
    data: dict
    is_error: bool

    model_config = {"from_attributes": True}


class TimelinePage(BaseModel):
    items: list[SnapshotResponse]
    next_cursor: Optional[int] = None
    total: int


@router.get("/crypto/workspaces/{search_space_id}/watchlist", response_model=list[CryptoProjectResponse])
async def get_workspace_watchlist(
    search_space_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Returns crypto projects tracked by this workspace, ordered by pin then recency."""
    await check_search_space_access(session, user, search_space_id)

    result = await session.execute(
        select(CryptoProject, SearchSpaceCryptoWatchlist)
        .join(SearchSpaceCryptoWatchlist, CryptoProject.id == SearchSpaceCryptoWatchlist.project_id)
        .where(SearchSpaceCryptoWatchlist.search_space_id == search_space_id)
        .order_by(
            SearchSpaceCryptoWatchlist.pin_order.nulls_last(),
            SearchSpaceCryptoWatchlist.added_at.desc(),
        )
    )
    rows = result.fetchall()

    return [
        CryptoProjectResponse(
            id=project.id,
            project_id=project.project_id,
            symbol=project.symbol,
            name=project.name,
            coingecko_id=project.coingecko_id,
            defillama_slug=project.defillama_slug,
            added_at=watchlist.added_at,
            pin_order=watchlist.pin_order,
        )
        for project, watchlist in rows
    ]


async def _verify_project_access(session: AsyncSession, user: User, project_id: int) -> None:
    """Verify user has access to project via at least one workspace they're a member of."""
    result = await session.execute(
        select(SearchSpaceCryptoWatchlist.id)
        .join(
            SearchSpaceMembership,
            SearchSpaceCryptoWatchlist.search_space_id == SearchSpaceMembership.search_space_id,
        )
        .where(
            SearchSpaceCryptoWatchlist.project_id == project_id,
            SearchSpaceMembership.user_id == user.id,
        )
        .limit(1)
    )
    if result.scalar() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/crypto/projects/{project_id}/timeline", response_model=TimelinePage)
async def get_project_timeline(
    project_id: int,
    category: Optional[str] = Query(None, description="Filter by data_category"),
    since: Optional[datetime] = Query(None, description="ISO 8601 start datetime (UTC)"),
    cursor: Optional[int] = Query(None, description="Pagination cursor (last snapshot id)"),
    limit: int = Query(100, ge=1, le=100),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Returns historical snapshots for a crypto project, newest first. Cursor-based pagination."""
    await _verify_project_access(session, user, project_id)

    # Normalize since to UTC-aware to prevent silent misbehavior vs TIMESTAMP WITH TIME ZONE
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    base_filters = [
        CryptoDataSnapshot.project_id == project_id,
        CryptoDataSnapshot.is_error.is_(False),
    ]
    if category:
        base_filters.append(CryptoDataSnapshot.data_category == category)
    if since:
        base_filters.append(CryptoDataSnapshot.fetched_at >= since)

    q = select(CryptoDataSnapshot).where(*base_filters)
    if cursor:
        q = q.where(CryptoDataSnapshot.id < cursor)

    # Secondary sort by id DESC ensures stable ordering when fetched_at ties
    q = q.order_by(CryptoDataSnapshot.fetched_at.desc(), CryptoDataSnapshot.id.desc()).limit(limit + 1)

    result = await session.execute(q)
    snapshots = list(result.scalars().all())

    has_more = len(snapshots) > limit
    items = snapshots[:limit]
    next_cursor = items[-1].id if has_more else None

    # Count uses same base filters (category + since) for accurate total
    count_q = select(func.count()).select_from(CryptoDataSnapshot).where(*base_filters)
    total = (await session.execute(count_q)).scalar() or 0

    return TimelinePage(
        items=[
            SnapshotResponse(
                id=s.id,
                data_category=s.data_category,
                tool_name=s.tool_name,
                api_source=s.api_source,
                fetched_at=s.fetched_at,
                expires_at=s.expires_at,
                data=s.data,
                is_error=s.is_error,
            )
            for s in items
        ],
        next_cursor=next_cursor,
        total=total,
    )
