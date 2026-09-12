"""
RBAC (Role-Based Access Control) routes for managing roles, memberships, and invites.

Endpoints:
- /workspaces/{workspace_id}/roles - CRUD for roles
- /workspaces/{workspace_id}/members - CRUD for memberships
- /workspaces/{workspace_id}/invites - CRUD for invites
- /invites/{invite_code}/info - Get invite info (public)
- /invites/accept - Accept an invite
- /permissions - List all available permissions
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Permission,
    WorkspaceInvite,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.schemas import (
    InviteAcceptRequest,
    InviteAcceptResponse,
    InviteCreate,
    InviteInfoResponse,
    InviteRead,
    InviteUpdate,
)
from app.services.workspace_limits import workspace_limit_service
from app.users import get_auth_context
from app.utils.rbac import (
    check_permission,
    generate_invite_code,
    get_default_role,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ============ Invite Endpoints ============


@router.post(
    "/workspaces/{workspace_id}/invites",
    response_model=InviteRead,
)
async def create_invite(
    workspace_id: int,
    invite_data: InviteCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Create a new invite link for a workspace.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to create invites",
        )

        # Enforce workspace member limit before creating the invite.
        await workspace_limit_service.check_member_limit(
            session, workspace_id, additional=1
        )

        # Verify role exists if specified
        if invite_data.role_id:
            role_result = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.id == invite_data.role_id,
                    WorkspaceRole.workspace_id == workspace_id,
                )
            )
            if not role_result.scalars().first():
                raise HTTPException(
                    status_code=404,
                    detail="Role not found in this workspace",
                )

        db_invite = WorkspaceInvite(
            **invite_data.model_dump(),
            invite_code=generate_invite_code(),
            workspace_id=workspace_id,
            created_by_id=user.id,
        )
        session.add(db_invite)
        await session.commit()

        # Reload with role
        result = await session.execute(
            select(WorkspaceInvite)
            .options(selectinload(WorkspaceInvite.role))
            .filter(WorkspaceInvite.id == db_invite.id)
        )
        db_invite = result.scalars().first()

        return db_invite

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create invite: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/invites",
    response_model=list[InviteRead],
)
async def list_invites(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all invites for a workspace.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to view invites",
        )

        result = await session.execute(
            select(WorkspaceInvite)
            .options(selectinload(WorkspaceInvite.role))
            .filter(WorkspaceInvite.workspace_id == workspace_id)
        )
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch invites: {e!s}"
        ) from e


@router.put(
    "/workspaces/{workspace_id}/invites/{invite_id}",
    response_model=InviteRead,
)
async def update_invite(
    workspace_id: int,
    invite_id: int,
    invite_update: InviteUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update an invite.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to update invites",
        )

        result = await session.execute(
            select(WorkspaceInvite)
            .options(selectinload(WorkspaceInvite.role))
            .filter(
                WorkspaceInvite.id == invite_id,
                WorkspaceInvite.workspace_id == workspace_id,
            )
        )
        db_invite = result.scalars().first()

        if not db_invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        update_data = invite_update.model_dump(exclude_unset=True)

        # Verify role exists if updating role_id
        if update_data.get("role_id"):
            role_result = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.id == update_data["role_id"],
                    WorkspaceRole.workspace_id == workspace_id,
                )
            )
            if not role_result.scalars().first():
                raise HTTPException(
                    status_code=404,
                    detail="Role not found in this workspace",
                )

        for key, value in update_data.items():
            setattr(db_invite, key, value)

        await session.commit()
        await session.refresh(db_invite)
        return db_invite

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update invite: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def revoke_invite(
    workspace_id: int,
    invite_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Revoke (delete) an invite.
    Requires MEMBERS_INVITE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.MEMBERS_INVITE.value,
            "You don't have permission to revoke invites",
        )

        result = await session.execute(
            select(WorkspaceInvite).filter(
                WorkspaceInvite.id == invite_id,
                WorkspaceInvite.workspace_id == workspace_id,
            )
        )
        db_invite = result.scalars().first()

        if not db_invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        await session.delete(db_invite)
        await session.commit()
        return {"message": "Invite revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to revoke invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to revoke invite: {e!s}"
        ) from e


# ============ Public Invite Endpoints ============


@router.get("/invites/{invite_code}/info", response_model=InviteInfoResponse)
async def get_invite_info(
    invite_code: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get information about an invite (public endpoint, no auth required).
    Returns minimal info for displaying on invite acceptance page.
    """
    try:
        result = await session.execute(
            select(WorkspaceInvite)
            .options(
                selectinload(WorkspaceInvite.role),
                selectinload(WorkspaceInvite.workspace),
            )
            .filter(WorkspaceInvite.invite_code == invite_code)
        )
        invite = result.scalars().first()

        if not invite:
            return InviteInfoResponse(
                workspace_name="",
                role_name=None,
                is_valid=False,
                message="Invite not found",
            )

        # Check if invite is still valid
        if not invite.is_active:
            return InviteInfoResponse(
                workspace_name=invite.workspace.name if invite.workspace else "",
                role_name=invite.role.name if invite.role else None,
                is_valid=False,
                message="This invite is no longer active",
            )

        if invite.expires_at and invite.expires_at < datetime.now(UTC):
            return InviteInfoResponse(
                workspace_name=invite.workspace.name if invite.workspace else "",
                role_name=invite.role.name if invite.role else None,
                is_valid=False,
                message="This invite has expired",
            )

        if invite.max_uses and invite.uses_count >= invite.max_uses:
            return InviteInfoResponse(
                workspace_name=invite.workspace.name if invite.workspace else "",
                role_name=invite.role.name if invite.role else None,
                is_valid=False,
                message="This invite has reached its maximum uses",
            )

        return InviteInfoResponse(
            workspace_name=invite.workspace.name if invite.workspace else "",
            role_name=invite.role.name if invite.role else "Default",
            is_valid=True,
        )

    except Exception as e:
        logger.error(f"Failed to get invite info: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get invite info: {e!s}"
        ) from e


@router.post("/invites/accept", response_model=InviteAcceptResponse)
async def accept_invite(
    request: InviteAcceptRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Accept an invite and join a workspace.
    """
    try:
        result = await session.execute(
            select(WorkspaceInvite)
            .options(
                selectinload(WorkspaceInvite.role),
                selectinload(WorkspaceInvite.workspace),
            )
            .filter(WorkspaceInvite.invite_code == request.invite_code)
        )
        invite = result.scalars().first()

        if not invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        # Validate invite
        if not invite.is_active:
            raise HTTPException(
                status_code=400, detail="This invite is no longer active"
            )

        if invite.expires_at and invite.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=400, detail="This invite has expired")

        if invite.max_uses and invite.uses_count >= invite.max_uses:
            raise HTTPException(
                status_code=400, detail="This invite has reached its maximum uses"
            )

        # Check if user is already a member
        existing_membership = await session.execute(
            select(WorkspaceMembership).filter(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == invite.workspace_id,
            )
        )
        if existing_membership.scalars().first():
            raise HTTPException(
                status_code=400,
                detail="You are already a member of this workspace",
            )

        # Consume the invite use before counting. This ensures a single-use
        # invite is no longer counted as an active invite when we check the
        # member limit, preventing a false "limit exceeded" at the boundary.
        invite.uses_count += 1

        # Enforce workspace member limit before accepting.
        await workspace_limit_service.check_member_limit(
            session, invite.workspace_id, additional=1
        )

        # Determine role to assign
        role_id = invite.role_id
        if not role_id:
            # Use default role
            default_role = await get_default_role(session, invite.workspace_id)
            role_id = default_role.id if default_role else None

        # Create membership
        membership = WorkspaceMembership(
            user_id=user.id,
            workspace_id=invite.workspace_id,
            role_id=role_id,
            is_owner=False,
            invited_by_invite_id=invite.id,
        )
        session.add(membership)

        await session.commit()

        role_name = invite.role.name if invite.role else "Default"
        workspace_name = invite.workspace.name if invite.workspace else ""

        return InviteAcceptResponse(
            message="Successfully joined the workspace",
            workspace_id=invite.workspace_id,
            workspace_name=workspace_name,
            role_name=role_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to accept invite: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to accept invite: {e!s}"
        ) from e
