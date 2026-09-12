import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    Permission,
    get_async_session,
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
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

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
