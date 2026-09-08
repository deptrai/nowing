"""Routes for workspace memory browser and review flag (Story 29.5 / FR-104)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import MemorySourceType, Permission, get_async_session
from app.schemas.memory_browser import (
    MemoryBrowserCreatorListResponse,
    MemoryBrowserDetailResponse,
    MemoryBrowserListResponse,
    MemoryBrowserTimelineResponse,
    MemoryRelationListResponse,
    MemoryReviewQueueCreate,
    MemoryReviewQueueRead,
    MemoryVersionListResponse,
)
from app.services.memory.memory_browser_service import MemoryBrowserService
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


def _pat_client_id(auth: AuthContext) -> str | None:
    """Return the client_id bound to the authenticated PAT, if any."""
    return getattr(auth.pat, "client_id", None) if auth.pat else None


def _as_utc(dt: datetime | None) -> datetime | None:
    """Coerce a possibly-naive datetime to UTC-aware for timestamptz comparisons."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@router.get(
    "/workspaces/{workspace_id}/memory-browser",
    response_model=MemoryBrowserListResponse,
)
async def list_memories(
    workspace_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    source_types: str | None = Query(None),
    confidence_min: float | None = Query(None, ge=0.0, le=1.0),
    confidence_max: float | None = Query(None, ge=0.0, le=1.0),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    created_by: str | None = Query(None),
    keyword: str | None = Query(None),
    sort: str = Query("created_at", pattern="^(created_at|updated_at|confidence)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
    )
    try:
        created_by_uuid = uuid.UUID(created_by) if created_by else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid created_by UUID") from exc
    source_types_list = source_types.split(",") if source_types else None
    if source_types_list:
        try:
            source_types_list = [
                MemorySourceType[st.strip().upper()].value
                for st in source_types_list
                if st.strip()
            ]
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid source_type: {exc}") from exc
    service = MemoryBrowserService(session)
    try:
        return await service.list_memories(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            source_types=source_types_list,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            created_after=_as_utc(created_after),
            created_before=_as_utc(created_before),
            created_by=created_by_uuid,
            keyword=keyword,
            client_id=_pat_client_id(auth),
            sort=sort,
            sort_dir=sort_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/workspaces/{workspace_id}/memory-browser/creators",
    response_model=MemoryBrowserCreatorListResponse,
)
async def list_memory_creators(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Populate the creator filter dropdown (AC-2.4)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
    )
    service = MemoryBrowserService(session)
    return await service.list_creators(workspace_id)


@router.get(
    "/workspaces/{workspace_id}/memory-browser/timeline",
    response_model=MemoryBrowserTimelineResponse,
)
async def get_memory_timeline(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Research timeline view: memories grouped by research thread (AC-4)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
    )
    service = MemoryBrowserService(session)
    return await service.get_timeline(workspace_id, client_id=_pat_client_id(auth))


@router.get(
    "/workspaces/{workspace_id}/memory-browser/{memory_id}",
    response_model=MemoryBrowserDetailResponse,
)
async def get_memory_detail(
    workspace_id: int,
    memory_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
    )
    service = MemoryBrowserService(session)
    try:
        return await service.get_memory_detail(
            workspace_id, memory_id, client_id=_pat_client_id(auth)
        )
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message or "no result" in message:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again or report this issue if it persists.",
        ) from exc


@router.get(
    "/workspaces/{workspace_id}/memory-browser/{memory_id}/versions",
    response_model=MemoryVersionListResponse,
)
async def get_memory_versions(
    workspace_id: int,
    memory_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
    )
    service = MemoryBrowserService(session)
    try:
        return await service.get_memory_versions(
            workspace_id, memory_id, client_id=_pat_client_id(auth)
        )
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message or "no result" in message:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again or report this issue if it persists.",
        ) from exc


@router.get(
    "/workspaces/{workspace_id}/memory-browser/{memory_id}/relations",
    response_model=MemoryRelationListResponse,
)
async def get_memory_relations(
    workspace_id: int,
    memory_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
    )
    service = MemoryBrowserService(session)
    try:
        return await service.get_memory_relations(
            workspace_id, memory_id, client_id=_pat_client_id(auth)
        )
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message or "no result" in message:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again or report this issue if it persists.",
        ) from exc


@router.post(
    "/workspaces/{workspace_id}/memory-browser/{memory_id}/review-flag",
    response_model=MemoryReviewQueueRead,
    status_code=201,
)
async def flag_memory_for_review(
    workspace_id: int,
    memory_id: int,
    payload: MemoryReviewQueueCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_UPDATE.value,
    )
    service = MemoryBrowserService(session)
    try:
        return await service.flag_for_review(
            workspace_id=workspace_id,
            memory_id=memory_id,
            flag_reason=payload.flag_reason,
            flagged_by=auth.user.id,
            client_id=_pat_client_id(auth),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message or "no result" in message:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again or report this issue if it persists.",
        ) from exc
