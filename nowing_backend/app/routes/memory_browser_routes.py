"""Routes for workspace memory browser and review flag (Story 29.5 / FR-104)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session, Permission
from app.schemas.memory_browser import (
    MemoryBrowserListResponse,
    MemoryBrowserDetailResponse,
    MemoryReviewQueueRead,
)
from app.services.memory.memory_browser_service import MemoryBrowserService
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


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
    sort: str = Query("created_at"),
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
    created_by_uuid = uuid.UUID(created_by) if created_by else None
    source_types_list = source_types.split(",") if source_types else None
    service = MemoryBrowserService(session)
    try:
        return await service.list_memories(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            source_types=source_types_list,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            created_after=created_after,
            created_before=created_before,
            created_by=created_by_uuid,
            keyword=keyword,
            sort=sort,
            sort_dir=sort_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
        return await service.get_memory_detail(workspace_id, memory_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/workspaces/{workspace_id}/memory-browser/{memory_id}/flag",
    response_model=MemoryReviewQueueRead,
    status_code=201,
)
async def flag_memory_for_review(
    workspace_id: int,
    memory_id: int,
    payload: dict,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_UPDATE.value,
    )
    flag_reason = payload.get("flag_reason", "")
    service = MemoryBrowserService(session)
    try:
        return await service.flag_for_review(
            workspace_id=workspace_id,
            memory_id=memory_id,
            flag_reason=flag_reason,
            flagged_by=auth.user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
