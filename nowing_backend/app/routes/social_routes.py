"""Social monitored target management (Story 21.8)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, SocialMonitoredTarget, Workspace, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/social-monitored-targets")


SUPPORTED_PLATFORMS = [
    "facebook_group",
    "facebook_page",
    "twitter_keyword",
    "twitter_user",
    "tiktok_hashtag",
    "chotot_category",
    "shopee_keyword",
    "topcv_search",
    "vietnamworks_search",
    "linkedin_company",
    "batdongsan_category",
    "masothue_lookup",
    "b2b_registry_search",
]

_PLATFORM_PATTERN = f"^({'|'.join(SUPPORTED_PLATFORMS)})$"


from typing import Literal

SocialTargetStatus = Literal["active", "paused", "error", "disabled"]


class SocialTargetCreate(BaseModel):
    platform: str = Field(..., pattern=_PLATFORM_PATTERN)
    target_id: str = Field(..., min_length=1, max_length=255)
    target_name: str = Field(..., min_length=1, max_length=1000)
    target_url: str | None = None
    category: str = Field(default="general", min_length=1, max_length=50)
    is_active: bool = True
    realtime_stream: bool = False
    scrape_interval_minutes: int = Field(default=15, ge=1, le=10080)
    status: SocialTargetStatus = Field(default="active")
    proxy_url: str | None = None
    account_id: str | None = None


class SocialTargetUpdate(BaseModel):
    target_name: str | None = Field(None, min_length=1, max_length=1000)
    target_url: str | None = None
    category: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None
    realtime_stream: bool | None = None
    scrape_interval_minutes: int | None = Field(None, ge=1, le=10080)
    status: SocialTargetStatus | None = Field(None)
    proxy_url: str | None = None
    account_id: str | None = None


class SocialTargetRead(BaseModel):
    id: int
    workspace_id: int
    platform: str
    target_id: str
    target_name: str
    target_url: str | None
    category: str
    is_active: bool
    realtime_stream: bool
    scrape_interval_minutes: int
    status: str
    proxy_url: str | None
    account_id: str | None

    model_config = ConfigDict(from_attributes=True)


async def _get_target(
    session: AsyncSession,
    workspace_id: int,
    target_id: int,
) -> SocialMonitoredTarget:
    target = await session.get(SocialMonitoredTarget, target_id)
    if target is None or target.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        )
    return target


async def _require_permission(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
    permission: Permission,
    message: str,
) -> None:
    await check_permission(session, auth, workspace_id, permission.value, message)


@router.post(
    "",
    response_model=SocialTargetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_social_target(
    workspace_id: int,
    payload: SocialTargetCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SocialTargetRead:
    """Create a new social monitored target."""
    await _require_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE,
        "You don't have permission to create social targets in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    target = SocialMonitoredTarget(
        workspace_id=workspace_id,
        platform=payload.platform,
        target_id=payload.target_id,
        target_name=payload.target_name,
        target_url=payload.target_url,
        category=payload.category,
        is_active=payload.is_active,
        realtime_stream=payload.realtime_stream,
        scrape_interval_minutes=payload.scrape_interval_minutes,
        status=payload.status,
        proxy_url=payload.proxy_url,
        account_id=payload.account_id,
    )
    session.add(target)
    try:
        await session.commit()
        await session.refresh(target)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A target with platform={payload.platform} and target_id={payload.target_id} already exists",
        ) from exc

    return SocialTargetRead.model_validate(target)


@router.get(
    "",
    response_model=list[SocialTargetRead],
)
async def list_social_targets(
    workspace_id: int,
    platform: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[SocialTargetRead]:
    """List social monitored targets for a workspace.

    Results are paginated and ordered by id for determinism.
    """
    await _require_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ,
        "You don't have permission to view social targets in this workspace",
    )

    from sqlalchemy import select
    stmt = select(SocialMonitoredTarget).where(
        SocialMonitoredTarget.workspace_id == workspace_id
    )
    if platform:
        stmt = stmt.where(SocialMonitoredTarget.platform == platform)
    if is_active is not None:
        stmt = stmt.where(SocialMonitoredTarget.is_active.is_(is_active))
    stmt = stmt.order_by(SocialMonitoredTarget.id).limit(limit).offset(offset)

    result = await session.execute(stmt)
    targets = result.scalars().all()
    return [SocialTargetRead.model_validate(t) for t in targets]


@router.get(
    "/{target_id}",
    response_model=SocialTargetRead,
)
async def get_social_target(
    workspace_id: int,
    target_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SocialTargetRead:
    """Get a social monitored target."""
    await _require_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ,
        "You don't have permission to view social targets in this workspace",
    )

    target = await _get_target(session, workspace_id, target_id)
    return SocialTargetRead.model_validate(target)


@router.patch(
    "/{target_id}",
    response_model=SocialTargetRead,
)
async def update_social_target(
    workspace_id: int,
    target_id: int,
    payload: SocialTargetUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SocialTargetRead:
    """Update a social monitored target."""
    await _require_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE,
        "You don't have permission to update social targets in this workspace",
    )

    target = await _get_target(session, workspace_id, target_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)

    try:
        await session.commit()
        await session.refresh(target)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Target update conflicts with an existing target",
        ) from exc

    return SocialTargetRead.model_validate(target)


@router.delete(
    "/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_social_target(
    workspace_id: int,
    target_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a social monitored target and its posts."""
    await _require_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE,
        "You don't have permission to delete social targets in this workspace",
    )

    target = await _get_target(session, workspace_id, target_id)
    await session.delete(target)
    await session.commit()
