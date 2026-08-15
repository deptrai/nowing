"""Social monitored target management (Story 21.8)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, SocialMonitoredTarget, Workspace, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/social-monitored-targets")


class SocialTargetCreate(BaseModel):
    platform: str = Field(..., pattern=r"^(facebook_group|facebook_page|twitter_keyword|twitter_user)$")
    target_id: str = Field(..., min_length=1, max_length=255)
    target_name: str = Field(..., min_length=1, max_length=1000)
    target_url: str | None = None
    category: str = Field(default="general", max_length=50)
    is_active: bool = True
    realtime_stream: bool = False
    scrape_interval_minutes: int = Field(default=15, ge=1)
    status: str = Field(default="active", max_length=50)
    proxy_url: str | None = None


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

    model_config = ConfigDict(from_attributes=True)


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
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
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
