"""Routes for Workspace Lead Tables and Send/Export Hub (Story 21.13)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Workspace, WorkspaceTable, get_async_session
from app.schemas.workspace_table import (
    WorkspaceTableCreate,
    WorkspaceTableRead,
    WorkspaceTableUpdate,
)
from app.users import get_auth_context
from app.utils.rbac import Permission, check_permission

router = APIRouter(tags=["workspace-tables"])


@router.get(
    "/workspaces/{workspace_id}/tables",
    response_model=list[WorkspaceTableRead],
    status_code=status.HTTP_200_OK,
)
async def list_workspace_tables(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[WorkspaceTableRead]:
    """List all spreadsheet table tabs configured for the workspace (AC-1, AC-3)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view tables in this workspace",
    )

    stmt = (
        select(WorkspaceTable)
        .where(WorkspaceTable.workspace_id == workspace_id)
        .order_by(WorkspaceTable.created_at.asc())
    )
    result = await session.execute(stmt)
    tables = result.scalars().all()
    return [WorkspaceTableRead.model_validate(t) for t in tables]


@router.post(
    "/workspaces/{workspace_id}/tables",
    response_model=WorkspaceTableRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_table(
    workspace_id: int,
    payload: WorkspaceTableCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> WorkspaceTableRead:
    """Create a new spreadsheet table tab in the workspace (AC-3)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to create tables in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace {workspace_id} not found",
        )

    table = WorkspaceTable(
        workspace_id=workspace_id,
        name=payload.name,
        icon=payload.icon,
        filter_preset=payload.filter_preset,
        columns_config=payload.columns_config,
    )
    session.add(table)
    await session.commit()
    await session.refresh(table)

    return WorkspaceTableRead.model_validate(table)


@router.get(
    "/workspaces/{workspace_id}/tables/{table_id}",
    response_model=WorkspaceTableRead,
    status_code=status.HTTP_200_OK,
)
async def get_workspace_table(
    workspace_id: int,
    table_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> WorkspaceTableRead:
    """Get details of a specific workspace table (AC-1)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view tables in this workspace",
    )

    table = await session.get(WorkspaceTable, table_id)
    if not table or table.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table {table_id} not found in workspace {workspace_id}",
        )

    return WorkspaceTableRead.model_validate(table)


@router.patch(
    "/workspaces/{workspace_id}/tables/{table_id}",
    response_model=WorkspaceTableRead,
    status_code=status.HTTP_200_OK,
)
async def update_workspace_table(
    workspace_id: int,
    table_id: UUID,
    payload: WorkspaceTableUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> WorkspaceTableRead:
    """Update table configuration, name, icon or filter presets (AC-3)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to update tables in this workspace",
    )

    table = await session.get(WorkspaceTable, table_id)
    if not table or table.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table {table_id} not found in workspace {workspace_id}",
        )

    if payload.name is not None:
        table.name = payload.name
    if payload.icon is not None:
        table.icon = payload.icon
    if payload.filter_preset is not None:
        table.filter_preset = payload.filter_preset
    if payload.columns_config is not None:
        table.columns_config = payload.columns_config

    table.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(table)

    return WorkspaceTableRead.model_validate(table)


@router.delete(
    "/workspaces/{workspace_id}/tables/{table_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace_table(
    workspace_id: int,
    table_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    """Delete a workspace table tab (AC-3). Leads assigned to it remain intact with null table_id."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to delete tables in this workspace",
    )

    table = await session.get(WorkspaceTable, table_id)
    if not table or table.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table {table_id} not found in workspace {workspace_id}",
        )

    await session.delete(table)
    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)



