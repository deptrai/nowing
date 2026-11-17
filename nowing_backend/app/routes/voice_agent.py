"""Voice Agent & BYO-SIP Trunk Management API (Story 38.6 / Decree 91)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.voice_sip import (
    SipTrunkCreateRequest,
    SipTrunkResponse,
    SipTrunkUpdateRequest,
)
from app.services.voice.sip_manager import SipTrunkManager
from app.users import require_session_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/voice",
    tags=["voice_agent"],
)

_sip_manager = SipTrunkManager()


def _get_sip_manager() -> SipTrunkManager:
    return _sip_manager


async def _ensure_workspace_admin(
    auth: AuthContext,
    workspace_id: int,
    session: AsyncSession,
) -> None:
    """Verify caller has admin or owner permission on the target workspace.

    Superusers bypass workspace-level RBAC. Everyone else must hold an
    Owner/Admin membership role resolved from the database.
    """
    if getattr(auth.user, "is_superuser", False):
        return

    from sqlalchemy import select

    from app.db import WorkspaceMembership, WorkspaceRole

    stmt = (
        select(WorkspaceRole.name)
        .join(WorkspaceMembership, WorkspaceMembership.role_id == WorkspaceRole.id)
        .where(
            WorkspaceMembership.user_id == auth.user.id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    res = await session.execute(stmt)
    role_name = res.scalar_one_or_none()

    if not role_name or role_name.lower() not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Owner permission required to manage telephony credentials",
        )


@router.post(
    "/trunks",
    response_model=SipTrunkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new BYO-SIP Trunk",
)
async def create_sip_trunk(
    workspace_id: int,
    req: SipTrunkCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    mgr: SipTrunkManager = Depends(_get_sip_manager),
) -> SipTrunkResponse:
    """Register a new SIP trunk with AES-256-GCM encrypted password."""
    await _ensure_workspace_admin(auth, workspace_id, session)
    trunk = await mgr.create_trunk(session, workspace_id, req)
    await session.commit()
    await session.refresh(trunk)
    return SipTrunkResponse.model_validate(trunk)


@router.get(
    "/trunks",
    response_model=list[SipTrunkResponse],
    summary="List workspace SIP Trunks",
)
async def list_sip_trunks(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    mgr: SipTrunkManager = Depends(_get_sip_manager),
) -> list[SipTrunkResponse]:
    """List all SIP trunks for a workspace. Passwords are masked."""
    await _ensure_workspace_admin(auth, workspace_id, session)
    trunks = await mgr.list_trunks(session, workspace_id)
    return [SipTrunkResponse.model_validate(t) for t in trunks]


@router.get(
    "/trunks/{trunk_id}",
    response_model=SipTrunkResponse,
    summary="Get SIP Trunk details",
)
async def get_sip_trunk(
    workspace_id: int,
    trunk_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    mgr: SipTrunkManager = Depends(_get_sip_manager),
) -> SipTrunkResponse:
    """Get single SIP trunk by ID. Password is masked."""
    await _ensure_workspace_admin(auth, workspace_id, session)
    trunk = await mgr.get_trunk(session, workspace_id, trunk_id)
    if not trunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SIP Trunk {trunk_id} not found in workspace {workspace_id}",
        )
    return SipTrunkResponse.model_validate(trunk)


@router.put(
    "/trunks/{trunk_id}",
    response_model=SipTrunkResponse,
    summary="Update a SIP Trunk",
)
async def update_sip_trunk(
    workspace_id: int,
    trunk_id: UUID,
    req: SipTrunkUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    mgr: SipTrunkManager = Depends(_get_sip_manager),
) -> SipTrunkResponse:
    """Update SIP trunk settings and/or credentials."""
    await _ensure_workspace_admin(auth, workspace_id, session)
    trunk = await mgr.update_trunk(session, workspace_id, trunk_id, req)
    if not trunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SIP Trunk {trunk_id} not found in workspace {workspace_id}",
        )
    await session.commit()
    await session.refresh(trunk)
    return SipTrunkResponse.model_validate(trunk)


@router.delete(
    "/trunks/{trunk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a SIP Trunk",
)
async def delete_sip_trunk(
    workspace_id: int,
    trunk_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    mgr: SipTrunkManager = Depends(_get_sip_manager),
) -> None:
    """Delete a SIP trunk from the workspace."""
    await _ensure_workspace_admin(auth, workspace_id, session)
    deleted = await mgr.delete_trunk(session, workspace_id, trunk_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SIP Trunk {trunk_id} not found in workspace {workspace_id}",
        )
    await session.commit()


@router.post(
    "/trunks/{trunk_id}/set-default",
    response_model=SipTrunkResponse,
    summary="Promote trunk to workspace default",
)
async def set_default_sip_trunk(
    workspace_id: int,
    trunk_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
    mgr: SipTrunkManager = Depends(_get_sip_manager),
) -> SipTrunkResponse:
    """Make this trunk the default outbound line for the workspace."""
    await _ensure_workspace_admin(auth, workspace_id, session)
    trunk = await mgr.set_default_trunk(session, workspace_id, trunk_id)
    if not trunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SIP Trunk {trunk_id} not found in workspace {workspace_id}",
        )
    await session.commit()
    await session.refresh(trunk)
    return SipTrunkResponse.model_validate(trunk)
