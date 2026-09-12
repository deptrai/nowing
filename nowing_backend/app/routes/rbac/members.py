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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Permission,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.dependencies.auth import RequirePermission, RequireWorkspaceAccess
from app.schemas import (
    MembershipRead,
    MembershipUpdate,
    UserWorkspaceAccess,
)
from app.users import get_auth_context
from app.utils.rbac import get_user_permissions

logger = logging.getLogger(__name__)

router = APIRouter()

# ============ Membership Endpoints ============


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[MembershipRead],
)
async def list_members(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.MEMBERS_VIEW.value,
            "You don't have permission to view members",
        )
    ),
):
    """
    List all members of a workspace.
    Requires MEMBERS_VIEW permission.
    """
    try:

        result = await session.execute(
            select(WorkspaceMembership)
            .options(selectinload(WorkspaceMembership.role))
            .filter(WorkspaceMembership.workspace_id == workspace_id)
        )
        memberships = result.scalars().all()

        # Fetch user emails for each membership
        response = []
        for membership in memberships:
            user_result = await session.execute(
                select(User).filter(User.id == membership.user_id)
            )
            member_user = user_result.scalars().first()

            membership_dict = {
                "id": membership.id,
                "user_id": membership.user_id,
                "workspace_id": membership.workspace_id,
                "role_id": membership.role_id,
                "is_owner": membership.is_owner,
                "joined_at": membership.joined_at,
                "created_at": membership.created_at,
                "role": membership.role,
                "user_email": member_user.email if member_user else None,
                "user_display_name": member_user.display_name if member_user else None,
                "user_avatar_url": member_user.avatar_url if member_user else None,
                "user_last_login": member_user.last_login if member_user else None,
                "monthly_spend_cap_micros": membership.monthly_spend_cap_micros,
                "monthly_spent_micros": membership.monthly_spent_micros,
                "is_accepting_leads": membership.is_accepting_leads,
                "lead_capacity": membership.lead_capacity,
                "status": membership.status,
            }
            response.append(membership_dict)

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch members: {e!s}"
        ) from e


@router.put(
    "/workspaces/{workspace_id}/members/{membership_id}",
    response_model=MembershipRead,
)
async def update_member_role(
    workspace_id: int,
    membership_id: int,
    membership_update: MembershipUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.MEMBERS_MANAGE_ROLES.value,
            "You don't have permission to manage member roles",
        )
    ),
):
    """
    Update a member's role.
    Requires MEMBERS_MANAGE_ROLES permission.
    Cannot change owner's role.
    """
    try:

        result = await session.execute(
            select(WorkspaceMembership)
            .options(selectinload(WorkspaceMembership.role))
            .filter(
                WorkspaceMembership.id == membership_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        db_membership = result.scalars().first()

        if not db_membership:
            raise HTTPException(status_code=404, detail="Membership not found")

        # Cannot change owner's role
        if db_membership.is_owner:
            raise HTTPException(
                status_code=400,
                detail="Cannot change the owner's role",
            )

        # Verify the new role exists in this workspace
        if membership_update.role_id:
            role_result = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.id == membership_update.role_id,
                    WorkspaceRole.workspace_id == workspace_id,
                )
            )
            if not role_result.scalars().first():
                raise HTTPException(
                    status_code=404,
                    detail="Role not found in this workspace",
                )

        db_membership.role_id = membership_update.role_id
        await session.commit()
        await session.refresh(db_membership)

        # Fetch user email
        user_result = await session.execute(
            select(User).filter(User.id == db_membership.user_id)
        )
        member_user = user_result.scalars().first()

        return {
            "id": db_membership.id,
            "user_id": db_membership.user_id,
            "workspace_id": db_membership.workspace_id,
            "role_id": db_membership.role_id,
            "is_owner": db_membership.is_owner,
            "joined_at": db_membership.joined_at,
            "created_at": db_membership.created_at,
            "role": db_membership.role,
            "user_email": member_user.email if member_user else None,
            "user_last_login": member_user.last_login if member_user else None,
            "monthly_spend_cap_micros": db_membership.monthly_spend_cap_micros,
            "monthly_spent_micros": db_membership.monthly_spent_micros,
            "is_accepting_leads": db_membership.is_accepting_leads,
            "lead_capacity": db_membership.lead_capacity,
            "status": db_membership.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update member role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update member role: {e!s}"
        ) from e


# NOTE: /members/me must be defined BEFORE /members/{membership_id}
# because FastAPI matches routes in order, and "me" would otherwise
# be interpreted as a membership_id (causing a 422 validation error)
@router.delete("/workspaces/{workspace_id}/members/me")
async def leave_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Leave a workspace (remove own membership).
    Owners cannot leave their workspace.
    """
    try:
        result = await session.execute(
            select(WorkspaceMembership).filter(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        db_membership = result.scalars().first()

        if not db_membership:
            raise HTTPException(
                status_code=404,
                detail="You are not a member of this workspace",
            )

        if db_membership.is_owner:
            raise HTTPException(
                status_code=400,
                detail="Owners cannot leave their workspace. Transfer ownership first or delete the workspace.",
            )

        await session.delete(db_membership)
        await session.commit()
        return {"message": "Successfully left the workspace"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to leave workspace: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to leave workspace: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}/members/{membership_id}")
async def remove_member(
    workspace_id: int,
    membership_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.MEMBERS_REMOVE.value,
            "You don't have permission to remove members",
        )
    ),
):
    """
    Remove a member from a workspace.
    Requires MEMBERS_REMOVE permission.
    Cannot remove the owner.
    """
    try:

        result = await session.execute(
            select(WorkspaceMembership).filter(
                WorkspaceMembership.id == membership_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        db_membership = result.scalars().first()

        if not db_membership:
            raise HTTPException(status_code=404, detail="Membership not found")

        if db_membership.is_owner:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the owner from the workspace",
            )

        await session.delete(db_membership)
        await session.commit()
        return {"message": "Member removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to remove member: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to remove member: {e!s}"
        ) from e


# ============ User Access Info ============


@router.get(
    "/workspaces/{workspace_id}/my-access",
    response_model=UserWorkspaceAccess,
)
async def get_my_access(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    membership: WorkspaceMembership = Depends(RequireWorkspaceAccess()),
):
    user = auth.user
    """
    Get the current user's access info for a workspace.
    """
    try:

        # Get workspace name
        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        workspace = result.scalars().first()

        # Get permissions
        permissions = await get_user_permissions(session, user.id, workspace_id)

        return UserWorkspaceAccess(
            workspace_id=workspace_id,
            workspace_name=workspace.name if workspace else "",
            is_owner=membership.is_owner,
            role_name=membership.role.name if membership.role else None,
            permissions=permissions,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get access info: {e!s}"
        ) from e
