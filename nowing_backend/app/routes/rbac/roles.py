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

from app.auth.context import AuthContext
from app.db import (
    AuditEvent,
    Permission,
    WorkspaceRole,
    get_async_session,
)
from app.schemas import (
    PermissionInfo,
    PermissionsListResponse,
    RoleCreate,
    RoleRead,
    RoleUpdate,
)
from app.users import get_auth_context
from app.utils.rbac import (
    check_permission,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ============ Permissions Endpoints ============

# Human-readable descriptions for each permission
PERMISSION_DESCRIPTIONS = {
    # Documents
    "documents:create": "Add new documents, files, and content to the workspace",
    "documents:read": "View and search documents in the workspace",
    "documents:update": "Edit existing documents and their metadata",
    "documents:delete": "Remove documents from the workspace",
    # Chats
    "chats:create": "Start new AI chat conversations",
    "chats:read": "View chat history and conversations",
    "chats:update": "Edit chat titles and settings",
    "chats:delete": "Delete chat conversations",
    # Comments
    "comments:create": "Add comments and annotations to documents",
    "comments:read": "View comments on documents",
    "comments:delete": "Remove comments from documents",
    # LLM Configs
    "llm_configs:create": "Add new AI model configurations",
    "llm_configs:read": "View AI model settings and configurations",
    "llm_configs:update": "Modify AI model configurations",
    "llm_configs:delete": "Remove AI model configurations",
    # Podcasts
    "podcasts:create": "Generate new AI podcasts from content",
    "podcasts:read": "Listen to and view generated podcasts",
    "podcasts:update": "Edit podcast settings and metadata",
    "podcasts:delete": "Remove generated podcasts",
    # Connectors
    "connectors:create": "Set up new data source integrations",
    "connectors:read": "View configured data sources and their status",
    "connectors:update": "Modify data source configurations",
    "connectors:delete": "Remove data source integrations",
    # Logs
    "logs:read": "View activity logs and audit trail",
    "logs:delete": "Clear activity logs",
    # Members
    "members:invite": "Send invitations to new team members",
    "members:view": "View the list of team members",
    "members:remove": "Remove members from the workspace",
    "members:manage_roles": "Assign and change member roles",
    # Roles
    "roles:create": "Create new custom roles",
    "roles:read": "View available roles and their permissions",
    "roles:update": "Modify role permissions",
    "roles:delete": "Remove custom roles",
    # Settings
    "settings:view": "View workspace settings",
    "settings:update": "Modify workspace settings",
    "settings:delete": "Delete the entire workspace",
    # API access
    "api_access:manage": "Enable or disable programmatic API access for a workspace",
    # Automations
    "automations:create": "Create automations from chat or JSON",
    "automations:read": "View automations, their triggers, and run history",
    "automations:update": "Edit automations and manage their triggers",
    "automations:delete": "Remove automations from the workspace",
    "automations:execute": "Manually fire automations",
    # Analytics (Story 29.1)
    "analytics:read": "View workspace analytics & adoption metrics",
    # Billing (Story 29.1)
    "billing:read": "View workspace plans, credit balances, and invoices",
    "billing:manage": "Upgrade/downgrade plans and manage payment methods",
    # Sources & Tools (Story 29.1)
    "source:configure": "Enable, disable, and configure scraper/connector sources",
    "tools:enable": "Toggle MCP tools and agent tool configurations",
    # Memory (Story 29.1)
    "memory:read": "Search and recall long-term research memories",
    "memory:create": "Create research memory facts",
    "memory:update": "Edit research memory facts",
    "memory:delete": "Remove memory records",
    # Full access
    "*": "Full access to all features and settings",
}


@router.get("/permissions", response_model=PermissionsListResponse)
async def list_all_permissions(
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all available permissions that can be assigned to roles.
    """
    permissions = []
    for perm in Permission:
        # Extract category from permission value (e.g., "documents:read" -> "documents")
        category = perm.value.split(":")[0] if ":" in perm.value else "general"
        description = PERMISSION_DESCRIPTIONS.get(
            perm.value, f"Permission for {perm.value}"
        )

        permissions.append(
            PermissionInfo(
                value=perm.value,
                name=perm.name,
                category=category,
                description=description,
            )
        )

    return PermissionsListResponse(permissions=permissions)


# ============ Role Endpoints ============


@router.post(
    "/workspaces/{workspace_id}/roles",
    response_model=RoleRead,
)
async def create_role(
    workspace_id: int,
    role_data: RoleCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Create a new custom role in a workspace.
    Requires ROLES_CREATE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_CREATE.value,
            "You don't have permission to create roles",
        )

        # Reserved "Admin" name guard (RB-4)
        clean_name = role_data.name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=400,
                detail="Role name cannot be empty",
            )
        if clean_name.lower() == "admin":
            raise HTTPException(
                status_code=400,
                detail="The role name 'Admin' is reserved",
            )

        # Check if role with same name already exists
        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.workspace_id == workspace_id,
                WorkspaceRole.name == clean_name,
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A role with name '{role_data.name}' already exists in this workspace",
            )

        # Validate permissions & Owner ceiling (AD-51, INV-29.1)
        if Permission.FULL_ACCESS.value in role_data.permissions:
            raise HTTPException(
                status_code=400,
                detail="Custom roles cannot grant permissions exceeding Owner ceiling",
            )

        valid_permissions = {p.value for p in Permission if p != Permission.FULL_ACCESS}
        for perm in role_data.permissions:
            if perm not in valid_permissions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid permission: {perm}",
                )

        # If setting is_default to True, unset any existing default
        if role_data.is_default:
            existing_defaults = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.workspace_id == workspace_id,
                    WorkspaceRole.is_default == True,  # noqa: E712
                )
            )
            for existing in existing_defaults.scalars().all():
                existing.is_default = False

        role_dict = role_data.model_dump()
        role_dict["name"] = clean_name
        role_dict["permissions"] = list(dict.fromkeys(role_data.permissions))
        role_dict["is_system_role"] = False

        db_role = WorkspaceRole(
            **role_dict,
            workspace_id=workspace_id,
        )
        session.add(db_role)
        # Flush to populate db_role.id for the AuditEvent payload
        await session.flush()

        audit = AuditEvent(
            action="workspace.role.create",
            actor_id=auth.user.id if auth and auth.user else None,
            diff_payload={
                "workspace_id": workspace_id,
                "role_id": db_role.id,
                "role_name": db_role.name,
                "permissions": db_role.permissions,
            },
        )
        session.add(audit)
        await session.commit()
        await session.refresh(db_role)
        return db_role

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create role: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/roles",
    response_model=list[RoleRead],
)
async def list_roles(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all roles in a workspace.
    Requires ROLES_READ permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_READ.value,
            "You don't have permission to view roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(WorkspaceRole.workspace_id == workspace_id)
        )
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch roles: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/roles/{role_id}",
    response_model=RoleRead,
)
async def get_role(
    workspace_id: int,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a specific role by ID.
    Requires ROLES_READ permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_READ.value,
            "You don't have permission to view roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.id == role_id,
                WorkspaceRole.workspace_id == workspace_id,
            )
        )
        role = result.scalars().first()

        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        return role

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch role: {e!s}"
        ) from e


@router.put(
    "/workspaces/{workspace_id}/roles/{role_id}",
    response_model=RoleRead,
)
async def update_role(
    workspace_id: int,
    role_id: int,
    role_update: RoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update a role.
    Requires ROLES_UPDATE permission.
    System roles can only have their permissions updated, not name/description.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_UPDATE.value,
            "You don't have permission to update roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.id == role_id,
                WorkspaceRole.workspace_id == workspace_id,
            )
        )
        db_role = result.scalars().first()

        if not db_role:
            raise HTTPException(status_code=404, detail="Role not found")

        # System role protection (INV-29.1, AD-51)
        if db_role.is_system_role:
            raise HTTPException(
                status_code=403,
                detail="System roles cannot be modified or deleted",
            )

        update_data = role_update.model_dump(exclude_unset=True)

        # Reserved "Admin" name guard (RB-4)
        if "name" in update_data and update_data["name"] is not None:
            clean_name = update_data["name"].strip()
            if not clean_name:
                raise HTTPException(
                    status_code=400,
                    detail="Role name cannot be empty",
                )
            if clean_name.lower() == "admin":
                raise HTTPException(
                    status_code=400,
                    detail="The role name 'Admin' is reserved",
                )
            update_data["name"] = clean_name

        # Check for name conflict if updating name
        if "name" in update_data and update_data["name"] != db_role.name:
            existing = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.workspace_id == workspace_id,
                    WorkspaceRole.name == update_data["name"],
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=409,
                    detail=f"A role with name '{update_data['name']}' already exists",
                )

        # Validate permissions & Owner ceiling if provided
        if "permissions" in update_data and update_data["permissions"] is not None:
            if Permission.FULL_ACCESS.value in update_data["permissions"]:
                raise HTTPException(
                    status_code=400,
                    detail="Custom roles cannot grant permissions exceeding Owner ceiling",
                )
            valid_permissions = {
                p.value for p in Permission if p != Permission.FULL_ACCESS
            }
            for perm in update_data["permissions"]:
                if perm not in valid_permissions:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid permission: {perm}",
                    )
            update_data["permissions"] = list(dict.fromkeys(update_data["permissions"]))

        # Handle is_default change
        if update_data.get("is_default") and not db_role.is_default:
            # Unset existing default
            existing_defaults = await session.execute(
                select(WorkspaceRole).filter(
                    WorkspaceRole.workspace_id == workspace_id,
                    WorkspaceRole.is_default == True,  # noqa: E712
                )
            )
            for existing in existing_defaults.scalars().all():
                existing.is_default = False

        for key, value in update_data.items():
            setattr(db_role, key, value)

        audit = AuditEvent(
            action="workspace.role.update",
            actor_id=auth.user.id if auth and auth.user else None,
            diff_payload={
                "workspace_id": workspace_id,
                "role_id": db_role.id,
                "role_name": db_role.name,
                "permissions": db_role.permissions,
            },
        )
        session.add(audit)
        await session.commit()
        await session.refresh(db_role)
        return db_role

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update role: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}/roles/{role_id}")
async def delete_role(
    workspace_id: int,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a custom role.
    Requires ROLES_DELETE permission.
    System roles cannot be deleted.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.ROLES_DELETE.value,
            "You don't have permission to delete roles",
        )

        result = await session.execute(
            select(WorkspaceRole).filter(
                WorkspaceRole.id == role_id,
                WorkspaceRole.workspace_id == workspace_id,
            )
        )
        db_role = result.scalars().first()

        if not db_role:
            raise HTTPException(status_code=404, detail="Role not found")

        if db_role.is_system_role:
            raise HTTPException(
                status_code=403,
                detail="System roles cannot be modified or deleted",
            )

        audit = AuditEvent(
            action="workspace.role.delete",
            actor_id=auth.user.id if auth and auth.user else None,
            diff_payload={
                "workspace_id": workspace_id,
                "role_id": db_role.id,
                "role_name": db_role.name,
                "permissions": db_role.permissions,
            },
        )
        session.add(audit)
        await session.delete(db_role)
        await session.commit()
        return {"message": "Role deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete role: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete role: {e!s}"
        ) from e
