"""User-facing routes for active in-app broadcast announcements (Story 25.6)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import WorkspaceMembership, get_async_session
from app.schemas.broadcasts import BroadcastActiveRead
from app.services.broadcast_service import BroadcastService
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])


@router.get(
    "/active",
    response_model=list[BroadcastActiveRead],
    summary="Get active broadcast announcement banners for the current user and workspace",
)
async def get_active_broadcasts(
    auth: Annotated[AuthContext, Depends(require_session_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    workspace_id: Annotated[
        int | None, Query(description="Current workspace ID context")
    ] = None,
) -> list[BroadcastActiveRead]:
    """Return active banners matching the current user's workspace targeting."""
    if workspace_id is not None:
        # Verify the user is a member of the requested workspace
        membership = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == auth.user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        if membership.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace",
            )

    service = BroadcastService(session)
    active_rows = await service.get_active_broadcasts(workspace_id=workspace_id)
    return [
        BroadcastActiveRead(
            id=r.id,
            title=r.title,
            message=r.message,
            banner_type=r.banner_type,
            dismissible=r.dismissible,
        )
        for r in active_rows
    ]
