---
storyId: 10.5
storyTitle: Workspace Watchlist & Timeline REST API
epicParent: epic-10-crypto-data-layer
depends: [Story 10.1]
relatedFRs: [FR40]
relatedNFRs: []
priority: P2
estimatedEffort: 2-3 days
status: done
createdAt: 2026-04-29
author: Winston (Architect)
---

# Story 10.5: Workspace Watchlist & Timeline REST API

## User Story

**As a** workspace member,
**I want** REST endpoints to access my workspace's tracked crypto projects and their historical data timeline,
**So that** future dashboard features (token tracker, price history chart) can consume this data without re-fetching from external APIs.

---

## Context

Stories 10.1-10.4 build the data collection layer. Story 10.5 exposes it via REST API. This is read-only — no write endpoints needed (data is written by the cache middleware, not by users directly).

The `search_space_crypto_watchlist` table is populated automatically when `CryptoDataCacheMiddleware` processes tool calls for tokens (upsert on each cache write). This story adds the query endpoints on top.

---

## Deliverables

### 📄 Files to Create (1 file)

#### `nowing_backend/app/routes/crypto_data_routes.py`

```python
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/crypto", tags=["crypto-data"])


class CryptoProjectResponse(BaseModel):
    id: int
    project_id: str
    symbol: Optional[str]
    name: Optional[str]
    coingecko_id: Optional[str]
    defillama_slug: Optional[str]
    added_at: datetime
    pin_order: Optional[int]

    class Config:
        from_attributes = True


class SnapshotResponse(BaseModel):
    id: int
    data_category: str
    tool_name: str
    api_source: str
    fetched_at: datetime
    expires_at: datetime
    data: dict
    is_error: bool

    class Config:
        from_attributes = True


class TimelinePage(BaseModel):
    items: list[SnapshotResponse]
    next_cursor: Optional[int]  # last snapshot id for pagination
    total: int


@router.get("/workspaces/{search_space_id}/watchlist", response_model=list[CryptoProjectResponse])
async def get_workspace_watchlist(
    search_space_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Returns crypto projects tracked by this workspace.
    Automatically populated as users query tokens.
    """
    # Verify user is member of search_space_id
    await verify_search_space_access(search_space_id, current_user, db)

    result = await db.execute(
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
            **project.__dict__,
            added_at=watchlist.added_at,
            pin_order=watchlist.pin_order,
        )
        for project, watchlist in rows
    ]


@router.get("/projects/{project_id}/timeline", response_model=TimelinePage)
async def get_project_timeline(
    project_id: int,
    category: Optional[str] = Query(None, description="Filter by data_category"),
    since: Optional[datetime] = Query(None, description="ISO 8601 start datetime"),
    cursor: Optional[int] = Query(None, description="Pagination cursor (last snapshot id)"),
    limit: int = Query(100, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Returns historical snapshots for a crypto project.
    Cursor-based pagination via snapshot id.
    """
    # Build query
    q = select(CryptoDataSnapshot).where(
        CryptoDataSnapshot.project_id == project_id,
        CryptoDataSnapshot.is_error == False,
    )
    if category:
        q = q.where(CryptoDataSnapshot.data_category == category)
    if since:
        q = q.where(CryptoDataSnapshot.fetched_at >= since)
    if cursor:
        q = q.where(CryptoDataSnapshot.id < cursor)

    q = q.order_by(CryptoDataSnapshot.fetched_at.desc()).limit(limit + 1)

    result = await db.execute(q)
    snapshots = result.scalars().all()

    has_more = len(snapshots) > limit
    items = snapshots[:limit]
    next_cursor = items[-1].id if has_more else None

    # Count total (for display, not critical — can be approximate)
    count_q = select(func.count()).where(
        CryptoDataSnapshot.project_id == project_id,
        CryptoDataSnapshot.is_error == False,
    )
    total = (await db.execute(count_q)).scalar()

    return TimelinePage(
        items=[SnapshotResponse.from_orm(s) for s in items],
        next_cursor=next_cursor,
        total=total,
    )
```

### 📄 Files to Modify (1 file)

#### `nowing_backend/app/main.py` (or router aggregation file)

```python
from app.routes.crypto_data_routes import router as crypto_data_router
app.include_router(crypto_data_router)
```

---

## Acceptance Criteria

### AC1: Watchlist — returns workspace's tracked projects

**Given** workspace 42 has analyzed ETH, BTC, UNI (via chat, triggering cache writes)
**When** `GET /api/crypto/workspaces/42/watchlist` called by workspace member
**Then** returns list with ETH, BTC, UNI entries
**And** each entry has symbol, name, coingecko_id, added_at

### AC2: Watchlist — 403 for non-member

**Given** user is NOT member of workspace 42
**When** `GET /api/crypto/workspaces/42/watchlist`
**Then** returns 403

### AC3: Timeline — basic query

**Given** ETH (project_id=1) has 50 snapshots across categories
**When** `GET /api/crypto/projects/1/timeline`
**Then** returns up to 100 snapshots, newest first
**And** `next_cursor` is null (only 50 items < 100 limit)

### AC4: Timeline — category filter

**When** `GET /api/crypto/projects/1/timeline?category=price_realtime`
**Then** only `price_realtime` snapshots returned

### AC5: Timeline — cursor pagination

**Given** project has 250 snapshots
**When** `GET /api/crypto/projects/1/timeline?limit=100`
**Then** returns 100 items, `next_cursor = <last item id>`
**When** `GET /api/crypto/projects/1/timeline?limit=100&cursor=<next_cursor>`
**Then** returns next 100 items

### AC6: Timeline — since filter

**When** `GET /api/crypto/projects/1/timeline?since=2026-04-01T00:00:00Z`
**Then** only snapshots with `fetched_at >= 2026-04-01` returned

### AC7: Error snapshots excluded

**Given** DB has error snapshots (`is_error=True`) for project
**When** timeline queried
**Then** error snapshots NOT included in response

---

## Dev Notes

- Follow existing route file patterns for auth dependency injection — check other routes in `app/routes/` for the exact `Depends` usage
- `verify_search_space_access` — likely already exists as utility for other workspace routes, reuse it
- Response format: follow existing convention — check if app wraps all responses in `{"data": ..., "error": ..., "meta": ...}` format (epics.md mentions this convention)
- cursor-based pagination over offset-based: prevents duplicate results if new snapshots added between pages
- `data` field in SnapshotResponse is JSONB — FastAPI will serialize it as-is to JSON (no extra work needed)
- Don't expose snapshots across workspaces — project_id lookup must be scoped by user's accessible workspaces (via watchlist join)

---

## Dev Agent Record

**Implemented by:** Claude (claude-sonnet-4-6)
**Implementation date:** 2026-05-01

### Files Created
- `nowing_backend/app/routes/crypto_data_routes.py` — 2 endpoints: GET watchlist + GET timeline

### Files Modified
- `nowing_backend/app/routes/__init__.py` — import + include crypto_data_router
- `nowing_backend/tests/unit/routes/test_crypto_data_routes.py` — 7 unit tests (AC1-AC7)

### Implementation Notes
- Router uses no prefix on `APIRouter()` — full paths in decorators, `/api/v1` prefix added in `app.py`
- Used `current_active_user` + `get_async_session` + `check_search_space_access` (RBAC util)
- Timeline uses `id < cursor` cursor pagination, `limit+1` fetch to detect has_more
- `is_error.is_(False)` not `== False` to generate correct SQLAlchemy IS FALSE
- Test pattern: plain `TestClient(app)` (no `with`) to avoid event loop conflicts from lifespan

### Change Log
- AC1-AC7: all acceptance criteria implemented and verified via unit tests (7/7 pass)

### Status: review

---

### Review Findings (2026-05-01)

- [x] [Review][Patch] F1: Timeline endpoint thiếu authorization check — verify project_id thuộc workspace của user qua watchlist join [crypto_data_routes.py:90] — fixed: _verify_project_access via watchlist+membership join
- [x] [Review][Patch] F2: `total` count bỏ qua active filters `category` và `since` — trả sai total khi filter [crypto_data_routes.py:124] — fixed: count_q dùng chung base_filters
- [x] [Review][Patch] F3: Cursor pagination không có tie-break trên `fetched_at` — duplicate/skip rows khi 2 snapshots có cùng timestamp [crypto_data_routes.py:115] — fixed: order_by(fetched_at.desc(), id.desc())
- [x] [Review][Patch] F7: `since` param không enforce timezone-aware — có thể silent misbehave vs TIMESTAMP WITH TIME ZONE column [crypto_data_routes.py:94] — fixed: normalize naive datetime to UTC
- [x] [Review][Patch] F8: `datetime` import đặt sau local imports, vi phạm PEP8/isort order [crypto_data_routes.py:18] — fixed: moved to top with stdlib imports
- [x] [Review][Defer] F4: `data: dict` expose raw unvalidated DB blob — sensitive fields không filtered — deferred, pre-existing design decision
- [x] [Review][Defer] F5: `category` filter không validate giá trị hợp lệ — typo silently trả 0 results — deferred, low priority
- [x] [Review][Defer] F6: Watchlist không có upper-bound limit — deferred, workspace size constraint không phải concern hiện tại
