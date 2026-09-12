import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Permission,
    WorkspaceLimit,
    WorkspaceMcpToolSetting,
    get_async_session,
)
from app.mcp_tools import (
    MCP_TOOL_CATALOG,
    MCP_TOOL_GROUP_MAP,
    MCP_TOOL_NAMES,
    MCP_TOOL_SYSTEM_TOOLS,
)
from app.schemas import (
    AutoExtractUsage,
    WorkspaceLimitsResponse,
    WorkspaceLimitUpdate,
    WorkspaceLimitUsage,
    WorkspaceMcpToolRead,
    WorkspaceMcpToolUpdate,
)
from app.services.memory.extract_budget import get_auto_extract_usage
from app.services.workspace_limits import workspace_limit_service
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()



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
