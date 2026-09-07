import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Permission,
    Workspace,
    WorkspaceLimit,
    WorkspaceMcpToolSetting,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
    get_default_roles_config,
)
from app.mcp_tools import (
    MCP_TOOL_CATALOG,
    MCP_TOOL_GROUP_MAP,
    MCP_TOOL_NAMES,
    MCP_TOOL_SYSTEM_TOOLS,
)
from app.routes.model_connections_routes import compute_llm_setup_status
from app.schemas import (
    AutoExtractUsage,
    PlanDefinitionRead,
    SubscriptionChangeCreate,
    SubscriptionChangeRead,
    WorkspaceApiAccessUpdate,
    WorkspaceCreate,
    WorkspaceLimitsResponse,
    WorkspaceLimitUpdate,
    WorkspaceLimitUsage,
    WorkspaceMcpToolRead,
    WorkspaceMcpToolUpdate,
    WorkspaceRead,
    WorkspaceSubscriptionResponse,
    WorkspaceUpdate,
    WorkspaceWithStats,
)
from app.schemas.bulk_ops import (
    BulkOpErrorRead,
    CancelJobResponse,
    DryRunRequest,
    DryRunResponse,
    ExecuteRequest,
    ExecuteResponse,
    JobStatusResponse,
)
from app.services.bulk_ops_service import OWNER_ALLOWED_ACTIONS, bulk_ops_service
from app.services.memory.extract_budget import get_auto_extract_usage
from app.services.workspace_limits import workspace_limit_service
from app.users import allow_any_principal, get_auth_context, require_session_context
from app.utils.rbac import check_permission, check_workspace_access, is_workspace_owner

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
):
    """
    Get a specific workspace by ID.
    Requires SETTINGS_VIEW permission or membership.
    """
    try:
        # Check if user has access (is a member)
        await check_workspace_access(session, auth, workspace_id)

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
):
    """
    Update a workspace.
    Requires SETTINGS_UPDATE permission.
    """
    try:
        # Check permission (no row lock needed here)
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update this workspace",
        )

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

        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.API_ACCESS_MANAGE.value,
            "You don't have permission to manage API access for this workspace",
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


@router.get("/workspaces/{workspace_id}/limits", response_model=WorkspaceLimitsResponse)
async def get_workspace_limits(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get effective limits and current usage for a workspace.
    Requires SETTINGS_UPDATE permission (Owner-only by default).
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to view workspace limits",
        )

        limits = await workspace_limit_service.get_effective_limits(
            session, workspace_id
        )
        usage = await workspace_limit_service.get_usage_snapshot(session, workspace_id)
        auto_extract_usage = await get_auto_extract_usage(session, workspace_id)

        return WorkspaceLimitsResponse(
            plan_tier=limits.plan_tier,
            max_documents=limits.max_documents,
            max_members=limits.max_members,
            max_runs=limits.max_runs,
            max_storage_bytes=limits.max_storage_bytes,
            max_memory_count=limits.max_memory_count,
            max_memory_bytes=limits.max_memory_bytes,
            run_period_hours=limits.run_period_hours,
            auto_extract_item_cap=limits.auto_extract_item_cap,
            auto_extract_spend_cap_micros=limits.auto_extract_spend_cap_micros,
            auto_extract_wallet_pre_check=limits.auto_extract_wallet_pre_check,
            news_entity_extraction_item_cap=limits.news_entity_extraction_item_cap,
            news_entity_extraction_spend_cap_micros=limits.news_entity_extraction_spend_cap_micros,
            news_entity_extraction_wallet_pre_check=limits.news_entity_extraction_wallet_pre_check,
            max_monthly_credits=limits.max_monthly_credits,
            max_sources=limits.max_sources,
            support_level=limits.support_level,
            price_micros=limits.price_micros,
            currency=limits.currency,
            auto_extract_usage=AutoExtractUsage(**auto_extract_usage),
            usage=WorkspaceLimitUsage(**usage),
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch workspace limits: {e!s}"
        ) from e


@router.put("/workspaces/{workspace_id}/limits", response_model=WorkspaceLimitsResponse)
async def update_workspace_limits(
    workspace_id: int,
    body: WorkspaceLimitUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update workspace-specific auto-extract budget caps.

    Requires SETTINGS_UPDATE permission (Owner-only by default).
    Only ``auto_extract_*`` fields are exposed for owner editing.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update workspace limits",
        )

        result = await session.execute(
            select(WorkspaceLimit).where(
                WorkspaceLimit.workspace_id == workspace_id,
                WorkspaceLimit.plan_tier.is_(None),
            )
        )
        override = result.scalars().first()
        if override is None:
            override = WorkspaceLimit(workspace_id=workspace_id)
            session.add(override)

        # Only overwrite supplied fields; keep existing overrides for others.
        if body.max_memory_count is not None:
            override.max_memory_count = body.max_memory_count
        if body.max_memory_bytes is not None:
            override.max_memory_bytes = body.max_memory_bytes
        if body.auto_extract_item_cap is not None:
            override.auto_extract_item_cap = body.auto_extract_item_cap
        if body.auto_extract_spend_cap_micros is not None:
            override.auto_extract_spend_cap_micros = body.auto_extract_spend_cap_micros
        if body.auto_extract_wallet_pre_check is not None:
            override.auto_extract_wallet_pre_check = body.auto_extract_wallet_pre_check
        if body.news_entity_extraction_item_cap is not None:
            override.news_entity_extraction_item_cap = (
                body.news_entity_extraction_item_cap
            )
        if body.news_entity_extraction_spend_cap_micros is not None:
            override.news_entity_extraction_spend_cap_micros = (
                body.news_entity_extraction_spend_cap_micros
            )
        if body.news_entity_extraction_wallet_pre_check is not None:
            override.news_entity_extraction_wallet_pre_check = (
                body.news_entity_extraction_wallet_pre_check
            )
        if body.max_monthly_credits is not None:
            override.max_monthly_credits = body.max_monthly_credits
        if body.max_sources is not None:
            override.max_sources = body.max_sources

        await session.commit()

        limits = await workspace_limit_service.get_effective_limits(
            session, workspace_id
        )
        usage = await workspace_limit_service.get_usage_snapshot(session, workspace_id)
        auto_extract_usage = await get_auto_extract_usage(session, workspace_id)

        return WorkspaceLimitsResponse(
            plan_tier=limits.plan_tier,
            max_documents=limits.max_documents,
            max_members=limits.max_members,
            max_runs=limits.max_runs,
            max_storage_bytes=limits.max_storage_bytes,
            max_memory_count=limits.max_memory_count,
            max_memory_bytes=limits.max_memory_bytes,
            run_period_hours=limits.run_period_hours,
            auto_extract_item_cap=limits.auto_extract_item_cap,
            auto_extract_spend_cap_micros=limits.auto_extract_spend_cap_micros,
            auto_extract_wallet_pre_check=limits.auto_extract_wallet_pre_check,
            news_entity_extraction_item_cap=limits.news_entity_extraction_item_cap,
            news_entity_extraction_spend_cap_micros=limits.news_entity_extraction_spend_cap_micros,
            news_entity_extraction_wallet_pre_check=limits.news_entity_extraction_wallet_pre_check,
            max_monthly_credits=limits.max_monthly_credits,
            max_sources=limits.max_sources,
            support_level=limits.support_level,
            price_micros=limits.price_micros,
            currency=limits.currency,
            auto_extract_usage=AutoExtractUsage(**auto_extract_usage),
            usage=WorkspaceLimitUsage(**usage),
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update workspace limits: {e!s}"
        ) from e


@router.delete("/workspaces/{workspace_id}", response_model=dict)
async def delete_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a workspace.
    Requires SETTINGS_DELETE permission (only owners have this by default).

    Heavy cascade deletion (documents, chunks, threads, etc.) is dispatched
    to Celery so the response is immediate and durable across API restarts.
    """
    try:
        # Check permission - only those with SETTINGS_DELETE can delete
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_DELETE.value,
            "You don't have permission to delete this workspace",
        )

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


@router.get("/workspaces/{workspace_id}/snapshots")
async def list_workspace_snapshots(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all public chat snapshots for a workspace.

    Requires PUBLIC_SHARING_VIEW permission.
    """
    from app.schemas.new_chat import PublicChatSnapshotsBySpaceResponse
    from app.services.public_chat_service import list_snapshots_for_workspace

    snapshots = await list_snapshots_for_workspace(
        session=session,
        workspace_id=workspace_id,
        auth=auth,
    )
    return PublicChatSnapshotsBySpaceResponse(snapshots=snapshots)


@router.get(
    "/workspaces/{workspace_id}/mcp-tools",
    response_model=list[WorkspaceMcpToolRead],
)
async def list_workspace_mcp_tools(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all built-in MCP tools for a workspace with their enabled state.

    Requires SETTINGS_VIEW permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view this workspace's settings",
        )

        result = await session.execute(
            select(WorkspaceMcpToolSetting).filter(
                WorkspaceMcpToolSetting.workspace_id == workspace_id
            )
        )
        stored_settings = {
            setting.tool_name: setting.enabled for setting in result.scalars().all()
        }

        return [
            WorkspaceMcpToolRead(
                name=tool["name"],
                enabled=stored_settings.get(tool["name"], True),
                is_system=tool["name"] in MCP_TOOL_SYSTEM_TOOLS,
                group=tool["group"],
            )
            for tool in MCP_TOOL_CATALOG
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list MCP tools: {e!s}",
        ) from e


@router.put(
    "/workspaces/{workspace_id}/mcp-tools/{tool_name}",
    response_model=WorkspaceMcpToolRead,
)
async def update_workspace_mcp_tool(
    workspace_id: int,
    tool_name: str,
    body: WorkspaceMcpToolUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Enable or disable a built-in MCP tool for a workspace.

    Requires SETTINGS_UPDATE permission.
    """
    try:
        if tool_name not in MCP_TOOL_NAMES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown tool: {tool_name}",
            )
        if tool_name in MCP_TOOL_SYSTEM_TOOLS:
            raise HTTPException(
                status_code=400,
                detail=f"System tool '{tool_name}' cannot be disabled",
            )

        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update this workspace's settings",
        )

        upsert = (
            insert(WorkspaceMcpToolSetting)
            .values(
                workspace_id=workspace_id,
                tool_name=tool_name,
                enabled=body.enabled,
            )
            .on_conflict_do_update(
                index_elements=["workspace_id", "tool_name"],
                set_={"enabled": body.enabled},
            )
            .returning(WorkspaceMcpToolSetting.enabled)
        )
        result = await session.execute(upsert)
        enabled = result.scalar_one()
        await session.commit()

        return WorkspaceMcpToolRead(
            name=tool_name,
            enabled=enabled,
            is_system=False,
            group=MCP_TOOL_GROUP_MAP[tool_name],
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update MCP tool: {e!s}",
        ) from e


# ----------------------------------------------------------------------
# Story 29.3: Workspace Subscriptions & Changes (FR-102, PM-1..PM-6)
# ----------------------------------------------------------------------


@router.get(
    "/workspaces/{workspace_id}/subscription",
    response_model=WorkspaceSubscriptionResponse,
)
async def get_workspace_subscription(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get current workspace subscription details, active pending/recent change,
    and available plan catalog definitions.

    Requires SETTINGS_VIEW permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view workspace subscription",
        )
        workspace = await session.get(Workspace, workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        limits = await workspace_limit_service.get_effective_limits(
            session, workspace_id
        )
        usage = await workspace_limit_service.get_usage_snapshot(session, workspace_id)
        auto_extract_usage = await get_auto_extract_usage(session, workspace_id)

        limits_resp = WorkspaceLimitsResponse(
            plan_tier=limits.plan_tier,
            max_documents=limits.max_documents,
            max_members=limits.max_members,
            max_runs=limits.max_runs,
            max_storage_bytes=limits.max_storage_bytes,
            max_memory_count=limits.max_memory_count,
            max_memory_bytes=limits.max_memory_bytes,
            run_period_hours=limits.run_period_hours,
            auto_extract_item_cap=limits.auto_extract_item_cap,
            auto_extract_spend_cap_micros=limits.auto_extract_spend_cap_micros,
            auto_extract_wallet_pre_check=limits.auto_extract_wallet_pre_check,
            news_entity_extraction_item_cap=limits.news_entity_extraction_item_cap,
            news_entity_extraction_spend_cap_micros=limits.news_entity_extraction_spend_cap_micros,
            news_entity_extraction_wallet_pre_check=limits.news_entity_extraction_wallet_pre_check,
            max_monthly_credits=limits.max_monthly_credits,
            max_sources=limits.max_sources,
            support_level=limits.support_level,
            price_micros=limits.price_micros,
            currency=limits.currency,
            auto_extract_usage=AutoExtractUsage(**auto_extract_usage),
            usage=WorkspaceLimitUsage(**usage),
        )

        changes = await workspace_limit_service.get_subscription_changes(
            session, workspace_id
        )
        active_change = None
        for c in changes:
            if c.status in ("pending", "active"):
                active_change = SubscriptionChangeRead.model_validate(c)
                break

        plans = await workspace_limit_service.get_plan_catalog(session)
        available_plans = [PlanDefinitionRead.model_validate(p) for p in plans]

        return WorkspaceSubscriptionResponse(
            current_plan=workspace.plan_tier or "free",
            limits=limits_resp,
            active_change=active_change,
            available_plans=available_plans,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch workspace subscription: {e!s}"
        ) from e


@router.post(
    "/workspaces/{workspace_id}/subscription-changes",
    response_model=SubscriptionChangeRead,
)
async def create_workspace_subscription_change(
    workspace_id: int,
    body: SubscriptionChangeCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Request a subscription plan change (upgrade/downgrade).

    Requires SETTINGS_UPDATE permission.
    Returns 409 if resource usage exceeds target plan limits.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to change workspace subscription",
        )
        change = await workspace_limit_service.create_subscription_change(
            session=session,
            workspace_id=workspace_id,
            to_plan=body.to_plan,
            immediate=body.immediate,
            user_id=auth.user_id,
            payment_method_id=body.payment_method_id,
        )
        await session.commit()
        await session.refresh(change)
        return SubscriptionChangeRead.model_validate(change)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to change subscription: {e!s}"
        ) from e


@router.get(
    "/workspaces/{workspace_id}/subscription-changes",
    response_model=list[SubscriptionChangeRead],
)
async def list_workspace_subscription_changes(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """List audit history of subscription changes for a workspace.

    Requires SETTINGS_VIEW permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view workspace subscription changes",
        )
        changes = await workspace_limit_service.get_subscription_changes(
            session=session,
            workspace_id=workspace_id,
        )
        return [SubscriptionChangeRead.model_validate(c) for c in changes]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list subscription changes: {e!s}"
        ) from e


@router.post(
    "/workspaces/{workspace_id}/subscription-changes/{change_id}/revert",
    response_model=SubscriptionChangeRead,
)
async def revert_workspace_subscription_change(
    workspace_id: int,
    change_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Revert a subscription plan change within the 7-day reversible window.

    Requires SETTINGS_UPDATE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to revert workspace subscription",
        )
        change = await workspace_limit_service.revert_subscription_change(
            session=session,
            workspace_id=workspace_id,
            change_id=change_id,
            user_id=auth.user_id,
        )
        await session.commit()
        await session.refresh(change)
        return SubscriptionChangeRead.model_validate(change)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to revert subscription change: {e!s}"
        ) from e


@router.post(
    "/workspaces/{workspace_id}/subscription-changes/{change_id}/cancel",
    response_model=SubscriptionChangeRead,
)
async def cancel_workspace_subscription_change(
    workspace_id: int,
    change_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Cancel a pending scheduled subscription plan change before it takes effect.

    Requires SETTINGS_UPDATE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to cancel workspace subscription change",
        )
        change = await workspace_limit_service.cancel_subscription_change(
            session=session,
            workspace_id=workspace_id,
            change_id=change_id,
            user_id=auth.user_id,
        )
        await session.commit()
        await session.refresh(change)
        return SubscriptionChangeRead.model_validate(change)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel subscription change: {e!s}"
        ) from e


# ----------------------------------------------------------------------
# Story 29.4: Workspace Owner-Scoped Bulk Operations (AD-54)
# ----------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/bulk-ops/dry-run",
    response_model=DryRunResponse,
)
async def workspace_bulk_op_dry_run(
    workspace_id: int,
    body: DryRunRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DryRunResponse:
    """Preview a bulk operation scoped to this workspace.

    Requires SETTINGS_UPDATE and MEMBERS_REMOVE permissions.
    """
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to perform bulk operations in this workspace",
    )
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMBERS_REMOVE.value,
        "You don't have permission to perform bulk operations in this workspace",
    )

    if body.action not in OWNER_ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action '{body.action.value}' is restricted to superadmins",
        )

    return await bulk_ops_service.dry_run(
        session=session,
        action=body.action,
        filter_spec=body.filter_spec,
        action_params=body.action_params,
        workspace_id=workspace_id,
    )


@router.post(
    "/workspaces/{workspace_id}/bulk-ops",
    response_model=ExecuteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def workspace_bulk_op_execute(
    workspace_id: int,
    body: ExecuteRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ExecuteResponse:
    """Execute a bulk operation scoped to this workspace.

    Requires SETTINGS_UPDATE and MEMBERS_REMOVE permissions and Idempotency-Key.
    """
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to perform bulk operations in this workspace",
    )
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMBERS_REMOVE.value,
        "You don't have permission to perform bulk operations in this workspace",
    )

    if body.action not in OWNER_ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action '{body.action.value}' is restricted to superadmins",
        )

    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'Idempotency-Key' is required",
        )

    return await bulk_ops_service.execute(
        session=session,
        action=body.action,
        filter_spec=body.filter_spec,
        action_params=body.action_params,
        actor=auth.user,
        workspace_id=workspace_id,
        idempotency_key=idempotency_key,
        password=body.password,
        mfa_token=body.mfa_token,
    )


@router.get(
    "/workspaces/{workspace_id}/bulk-ops/{job_id}",
    response_model=JobStatusResponse,
)
async def workspace_bulk_op_get_job(
    workspace_id: int,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> JobStatusResponse:
    """Poll progress for a workspace bulk operation job."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_VIEW.value,
        "You don't have permission to view bulk operations in this workspace",
    )
    return await bulk_ops_service.get_job(
        session=session,
        job_id=job_id,
        actor=auth.user,
        workspace_id=workspace_id,
    )


@router.post(
    "/workspaces/{workspace_id}/bulk-ops/{job_id}/cancel",
    response_model=CancelJobResponse,
)
async def workspace_bulk_op_cancel_job(
    workspace_id: int,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> CancelJobResponse:
    """Cancel a workspace bulk operation job."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to cancel bulk operations in this workspace",
    )
    return await bulk_ops_service.cancel_job(
        session=session,
        job_id=job_id,
        actor=auth.user,
        workspace_id=workspace_id,
    )


@router.get(
    "/workspaces/{workspace_id}/bulk-ops/{job_id}/errors",
    response_model=list[BulkOpErrorRead],
)
async def workspace_bulk_op_get_errors(
    workspace_id: int,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[BulkOpErrorRead]:
    """Retrieve error records for failed subjects in a workspace bulk job."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_VIEW.value,
        "You don't have permission to view bulk operation errors",
    )
    return await bulk_ops_service.get_job_errors(
        session=session,
        job_id=job_id,
        actor=auth.user,
        workspace_id=workspace_id,
    )

