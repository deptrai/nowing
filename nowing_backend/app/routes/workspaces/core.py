import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Permission,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
    get_default_roles_config,
)
from app.dependencies.auth import RequirePermission, RequireWorkspaceAccess
from app.routes.model_connections_routes import compute_llm_setup_status
from app.schemas import (
    WorkspaceApiAccessUpdate,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
    WorkspaceWithStats,
)
from app.users import allow_any_principal, get_auth_context, require_session_context
from app.utils.rbac import is_workspace_owner

logger = logging.getLogger(__name__)

router = APIRouter()


async def create_default_roles_and_membership(
    session: AsyncSession,
    workspace_id: int,
    owner_user_id,
) -> None:
    """
    Create default system roles for a workspace and add the owner as a member.

    Args:
        session: Database session
        workspace_id: The ID of the newly created workspace
        owner_user_id: The UUID of the user who created the workspace
    """
    # Create default roles
    default_roles = get_default_roles_config()
    owner_role_id = None

    for role_config in default_roles:
        db_role = WorkspaceRole(
            name=role_config["name"],
            description=role_config["description"],
            permissions=role_config["permissions"],
            is_default=role_config["is_default"],
            is_system_role=role_config["is_system_role"],
            workspace_id=workspace_id,
        )
        session.add(db_role)
        await session.flush()  # Get the ID

        if role_config["name"] == "Owner":
            owner_role_id = db_role.id

    # Create owner membership
    owner_membership = WorkspaceMembership(
        user_id=owner_user_id,
        workspace_id=workspace_id,
        role_id=owner_role_id,
        is_owner=True,
    )
    session.add(owner_membership)


@router.post("/workspaces", response_model=WorkspaceRead)
async def create_workspace(
    workspace: WorkspaceCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    user = auth.user
    try:
        workspace_data = workspace.model_dump()

        # citations_enabled defaults to True (handled by Pydantic schema)
        # qna_custom_instructions defaults to None/empty (handled by DB)

        db_workspace = Workspace(**workspace_data, user_id=user.id)
        session.add(db_workspace)
        await session.flush()  # Get the workspace ID

        # Create default roles and owner membership
        await create_default_roles_and_membership(session, db_workspace.id, user.id)

        # Auto-provision XActions connector for the workspace
        from app.services.xactions_connector_seed import (
            ensure_workspace_xactions_connector,
        )

        await ensure_workspace_xactions_connector(session, db_workspace.id, user.id)

        await session.commit()
        await session.refresh(db_workspace)

        response = WorkspaceRead.model_validate(db_workspace)
        response.llm_setup = await compute_llm_setup_status(
            session, auth, db_workspace.id
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create workspace: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create workspace: {e!s}"
        ) from e


@router.get("/workspaces", response_model=list[WorkspaceWithStats])
async def read_workspaces(
    skip: int = 0,
    limit: int = 200,
    owned_only: bool = False,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(allow_any_principal),
):
    user = auth.user
    """
    Get all workspaces the user has access to, with member count and ownership info.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        owned_only: If True, only return workspaces owned by the user.
                   If False (default), return all workspaces the user has access to.
    """
    try:
        # Exclude spaces that are pending background deletion
        not_deleting = ~Workspace.name.startswith("[DELETING] ")

        api_access_filter = (
            Workspace.api_access_enabled == True  # noqa: E712
            if auth.is_gated
            else True
        )

        if owned_only:
            # Return only workspaces where user is the original creator (user_id)
            result = await session.execute(
                select(Workspace)
                .filter(Workspace.user_id == user.id, not_deleting, api_access_filter)
                .order_by(Workspace.id.asc())
                .offset(skip)
                .limit(limit)
            )
        else:
            # Return all workspaces the user has membership in
            result = await session.execute(
                select(Workspace)
                .join(WorkspaceMembership)
                .filter(
                    WorkspaceMembership.user_id == user.id,
                    not_deleting,
                    api_access_filter,
                )
                .order_by(Workspace.id.asc())
                .offset(skip)
                .limit(limit)
            )

        workspaces = result.scalars().all()

        # Get member counts and ownership info for each workspace
        workspaces_with_stats = []
        for space in workspaces:
            # Get member count
            count_result = await session.execute(
                select(func.count(WorkspaceMembership.id)).filter(
                    WorkspaceMembership.workspace_id == space.id
                )
            )
            member_count = count_result.scalar() or 1

            # Check if current user is owner
            ownership_result = await session.execute(
                select(WorkspaceMembership).filter(
                    WorkspaceMembership.workspace_id == space.id,
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.is_owner == True,  # noqa: E712
                )
            )
            is_owner = ownership_result.scalars().first() is not None

            workspaces_with_stats.append(
                WorkspaceWithStats(
                    id=space.id,
                    name=space.name,
                    description=space.description,
                    vertical=space.vertical,
                    created_at=space.created_at,
                    user_id=space.user_id,
                    citations_enabled=space.citations_enabled,
                    api_access_enabled=space.api_access_enabled,
                    qna_custom_instructions=space.qna_custom_instructions,
                    document_retention_days=space.document_retention_days,
                    auto_archive_enabled=space.auto_archive_enabled,
                    document_retention_action=space.document_retention_action,
                    memory_retention_days=space.memory_retention_days,
                    memory_auto_archive_enabled=space.memory_auto_archive_enabled,
                    memory_retention_action=space.memory_retention_action,
                    memory_auto_extract_enabled=space.memory_auto_extract_enabled,
                    member_count=member_count,
                    is_owner=is_owner,
                )
            )

        return workspaces_with_stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch workspaces: {e!s}"
        ) from e


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceRead)
async def read_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(RequireWorkspaceAccess()),
):
    """
    Get a specific workspace by ID.
    Requires SETTINGS_VIEW permission or membership.
    """
    try:
        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        workspace = result.scalars().first()

        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        response = WorkspaceRead.model_validate(workspace)
        response.is_owner = await is_workspace_owner(
            session, auth.user.id, workspace_id
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch workspace: {e!s}"
        ) from e


@router.put("/workspaces/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    workspace_id: int,
    workspace_update: WorkspaceUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update this workspace",
        )
    ),
):
    """
    Update a workspace.
    Requires SETTINGS_UPDATE permission.
    """
    try:
        update_data = workspace_update.model_dump(exclude_unset=True)

        # Only serialize concurrent updates that touch retention settings.
        retention_fields = {
            "document_retention_days",
            "auto_archive_enabled",
            "document_retention_action",
            "memory_retention_days",
            "memory_auto_archive_enabled",
            "memory_retention_action",
        }
        touches_retention = bool(retention_fields & update_data.keys())

        if touches_retention:
            # Fail fast if another request holds the row lock too long.
            await session.execute(text("SET LOCAL lock_timeout = '10s'"))
            result = await session.execute(
                select(Workspace).filter(Workspace.id == workspace_id).with_for_update()
            )
        else:
            result = await session.execute(
                select(Workspace).filter(Workspace.id == workspace_id)
            )

        db_workspace = result.scalars().first()

        if not db_workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Compute effective final state for document retention fields.
        new_auto_archive = update_data.get(
            "auto_archive_enabled", db_workspace.auto_archive_enabled
        )
        new_days = update_data.get(
            "document_retention_days", db_workspace.document_retention_days
        )
        new_action = update_data.get(
            "document_retention_action", db_workspace.document_retention_action
        )

        # Reject explicit nulls for non-nullable retention fields.
        if "auto_archive_enabled" in update_data and new_auto_archive is None:
            raise HTTPException(
                status_code=400, detail="auto_archive_enabled cannot be null"
            )
        if "document_retention_action" in update_data and new_action is None:
            raise HTTPException(
                status_code=400, detail="document_retention_action cannot be null"
            )

        # Validate the final document retention invariant.
        if new_auto_archive:
            if new_days is None or not isinstance(new_days, int) or new_days <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="document_retention_days must be a positive integer when auto_archive_enabled is true",
                )
            if new_days > 36500:
                raise HTTPException(
                    status_code=400,
                    detail="document_retention_days must not exceed 36500 (100 years)",
                )
            if not new_action:
                raise HTTPException(
                    status_code=400,
                    detail="document_retention_action is required when auto_archive_enabled is true",
                )

        # Compute and validate memory retention fields (Story 28.5).
        new_mem_auto_archive = update_data.get(
            "memory_auto_archive_enabled", db_workspace.memory_auto_archive_enabled
        )
        new_mem_days = update_data.get(
            "memory_retention_days", db_workspace.memory_retention_days
        )
        new_mem_action = update_data.get(
            "memory_retention_action", db_workspace.memory_retention_action
        )

        if (
            "memory_auto_archive_enabled" in update_data
            and new_mem_auto_archive is None
        ):
            raise HTTPException(
                status_code=400, detail="memory_auto_archive_enabled cannot be null"
            )
        if "memory_retention_action" in update_data and new_mem_action is None:
            raise HTTPException(
                status_code=400, detail="memory_retention_action cannot be null"
            )

        if new_mem_auto_archive:
            if (
                new_mem_days is None
                or not isinstance(new_mem_days, int)
                or new_mem_days <= 0
            ):
                raise HTTPException(
                    status_code=400,
                    detail="memory_retention_days must be a positive integer when memory_auto_archive_enabled is true",
                )
            if new_mem_days > 36500:
                raise HTTPException(
                    status_code=400,
                    detail="memory_retention_days must not exceed 36500 (100 years)",
                )
            if not new_mem_action:
                raise HTTPException(
                    status_code=400,
                    detail="memory_retention_action is required when memory_auto_archive_enabled is true",
                )

        for key, value in update_data.items():
            setattr(db_workspace, key, value)
        await session.commit()
        await session.refresh(db_workspace)
        response = WorkspaceRead.model_validate(db_workspace)
        response.is_owner = await is_workspace_owner(
            session, auth.user.id, workspace_id
        )
        return response
    except HTTPException:
        await session.rollback()
        raise
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update workspace: {e!s}"
        ) from e


@router.put("/workspaces/{workspace_id}/api-access", response_model=WorkspaceRead)
async def update_workspace_api_access(
    workspace_id: int,
    body: WorkspaceApiAccessUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.API_ACCESS_MANAGE.value,
            "You don't have permission to manage API access for this workspace",
        )
    ),
):
    """
    Toggle programmatic API/PAT access for a workspace.
    Requires API_ACCESS_MANAGE permission.
    """
    try:
        if not auth.is_session:
            raise HTTPException(
                status_code=403,
                detail="This action requires an interactive session",
            )

        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        db_workspace = result.scalars().first()

        if not db_workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        db_workspace.api_access_enabled = body.api_access_enabled
        await session.commit()
        await session.refresh(db_workspace)
        return db_workspace
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update API access: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}", response_model=dict)
async def delete_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_DELETE.value,
            "You don't have permission to delete this workspace",
        )
    ),
):
    """
    Delete a workspace.
    Requires SETTINGS_DELETE permission (only owners have this by default).

    Heavy cascade deletion (documents, chunks, threads, etc.) is dispatched
    to Celery so the response is immediate and durable across API restarts.
    """
    try:
        result = await session.execute(
            select(Workspace).filter(Workspace.id == workspace_id)
        )
        db_workspace = result.scalars().first()

        if not db_workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        if (db_workspace.name or "").startswith("[DELETING] "):
            raise HTTPException(
                status_code=409,
                detail="Workspace is already being deleted.",
            )

        # Soft-delete marker (length-safe for String(100)) so users see pending state.
        prefix = "[DELETING] "
        max_len = 100
        available = max_len - len(prefix)
        base_name = db_workspace.name or ""
        db_workspace.name = f"{prefix}{base_name[:available]}"
        await session.commit()

        # Dispatch durable background deletion via Celery.
        # If queue dispatch fails, revert name to avoid stuck "[DELETING]" state.
        try:
            from app.tasks.celery_tasks.document_tasks import delete_workspace_task

            delete_workspace_task.delay(workspace_id)
        except Exception as dispatch_error:
            db_workspace.name = base_name
            await session.commit()
            raise HTTPException(
                status_code=503,
                detail="Failed to queue background deletion. Please try again.",
            ) from dispatch_error

        return {"message": "Workspace deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete workspace: {e!s}"
        ) from e
