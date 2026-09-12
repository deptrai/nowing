"""Governance console routes (Story 29.6 / FR-97).

Prefix: /workspaces/{workspace_id}/governance
Guards: workspace-scoped RBAC permissions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, WorkspaceMembership, get_async_session
from app.dependencies.auth import RequirePermission
from app.schemas.bulk_ops import CancelJobResponse, JobStatusResponse
from app.schemas.governance import (
    AuditLogFilter,
    AuditLogRead,
    DncRecordCreate,
    DncRecordRead,
    GovernanceOverviewRead,
    RetentionPolicyRead,
    RetentionPolicyUpdate,
    RightToDeleteRequest,
    RightToDeleteResponse,
    SourceRiskTierRead,
    SourceRiskTierUpdate,
    WorkspaceStatusRead,
)
from app.services.bulk_ops_service import BulkOpsService
from app.services.governance_service import GovernanceService
from app.users import get_auth_context
from app.utils.rbac import is_workspace_owner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/governance", tags=["governance"])


@router.get("", response_model=GovernanceOverviewRead)
async def get_governance_overview(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view governance settings",
        )
    ),
) -> GovernanceOverviewRead:
    """Return combined governance console payload (AC-1)."""
    svc = GovernanceService(session)
    return await svc.get_overview(workspace_id)


@router.put("/retention", response_model=RetentionPolicyRead)
async def update_retention_policy(
    workspace_id: int,
    payload: RetentionPolicyUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update governance settings",
        )
    ),
) -> RetentionPolicyRead:
    """Update workspace retention policy (AC-2/AC-3)."""
    svc = GovernanceService(session)
    return await svc.update_retention_policy(
        workspace_id, payload, actor_id=auth.user.id if auth.user else None
    )


@router.get("/source-risk-tiers", response_model=list[SourceRiskTierRead])
async def list_source_risk_tiers(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view governance settings",
        )
    ),
) -> list[SourceRiskTierRead]:
    """List configured source risk tiers (AC-3)."""
    svc = GovernanceService(session)
    return await svc.list_source_risk_tiers()


@router.put("/source-risk-tiers", response_model=SourceRiskTierRead)
async def upsert_source_risk_tier(
    workspace_id: int,
    payload: SourceRiskTierUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update governance settings",
        )
    ),
) -> SourceRiskTierRead:
    """Create or update a source risk tier; pause scraping on high risk (AC-5)."""
    svc = GovernanceService(session)
    return await svc.upsert_source_risk_tier(
        workspace_id, payload, actor_id=auth.user.id if auth.user else None
    )


@router.get("/dnc-records", response_model=list[DncRecordRead])
async def list_dnc_records(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view governance settings",
        )
    ),
) -> list[DncRecordRead]:
    """List workspace DNC records with global supersession flags (AC-6)."""
    svc = GovernanceService(session)
    return await svc.list_dnc_records(workspace_id)


@router.post("/dnc-records", response_model=DncRecordRead, status_code=201)
async def create_dnc_record(
    workspace_id: int,
    payload: DncRecordCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update governance settings",
        )
    ),
) -> DncRecordRead:
    """Create a workspace DNC record (AC-6)."""
    svc = GovernanceService(session)
    return await svc.create_dnc_record(
        workspace_id, payload, actor_id=auth.user.id if auth.user else None
    )


@router.delete("/dnc-records/{record_id}", status_code=204)
async def delete_dnc_record(
    workspace_id: int,
    record_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to update governance settings",
        )
    ),
) -> None:
    """Delete a workspace DNC record (AC-6)."""
    from uuid import UUID as _UUID

    try:
        _UUID(record_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="record_id must be a valid UUID"
        ) from exc

    svc = GovernanceService(session)
    await svc.delete_dnc_record(
        workspace_id, record_id, actor_id=auth.user.id if auth.user else None
    )


@router.post("/right-to-delete", response_model=RightToDeleteResponse | None)
async def right_to_delete(
    workspace_id: int,
    payload: RightToDeleteRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.MEMORY_DELETE.value,
            "You don't have permission to delete memories",
        )
    ),
) -> RightToDeleteResponse | None:
    """Right-to-delete single or bulk memory (AC-4)."""
    svc = GovernanceService(session)
    result = await svc.right_to_delete(
        workspace_id, payload, actor_id=auth.user.id if auth.user else None
    )
    # AC-4/5: single memory delete returns 204 No Content.
    if payload.type == "single_memory" and not payload.dry_run:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    return result


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_bulk_op_job(
    workspace_id: int,
    job_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.MEMORY_DELETE.value,
            "You don't have permission to view bulk delete jobs",
        )
    ),
) -> JobStatusResponse:
    """Fetch bulk operation job status scoped to this workspace (AC-4/4)."""
    from uuid import UUID as _UUID

    try:
        job_uuid = _UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="job_id must be a valid UUID") from exc

    if not auth.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    svc = BulkOpsService()
    return await svc.get_job(session, job_uuid, auth.user, workspace_id=workspace_id)


@router.post("/jobs/{job_id}/cancel", response_model=CancelJobResponse)
async def cancel_bulk_op_job(
    workspace_id: int,
    job_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.MEMORY_DELETE.value,
            "You don't have permission to cancel bulk delete jobs",
        )
    ),
) -> CancelJobResponse:
    """Cancel a queued or running bulk operation job in this workspace (AC-4/4)."""
    from uuid import UUID as _UUID

    try:
        job_uuid = _UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="job_id must be a valid UUID") from exc

    if not auth.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    svc = BulkOpsService()
    return await svc.cancel_job(session, job_uuid, auth.user, workspace_id=workspace_id)


@router.get("/audit-log", response_model=list[AuditLogRead])
async def list_audit_log(
    workspace_id: int,
    action_prefix: str | None = Query(default=None),
    created_after: str | None = Query(default=None),
    created_before: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_VIEW.value,
            "You don't have permission to view governance settings",
        )
    ),
) -> list[AuditLogRead]:
    """Query governance audit events for the workspace (AC-7)."""
    from datetime import datetime

    try:
        after_dt = datetime.fromisoformat(created_after) if created_after else None
        before_dt = datetime.fromisoformat(created_before) if created_before else None
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid ISO date format: {exc}"
        ) from exc

    filters = AuditLogFilter(
        action_prefix=action_prefix,
        created_after=after_dt,
        created_before=before_dt,
        page=page,
        page_size=page_size,
    )
    svc = GovernanceService(session)
    return await svc.list_audit_log(workspace_id, filters)


@router.post("/archive", response_model=WorkspaceStatusRead)
async def archive_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to archive this workspace",
        )
    ),
) -> WorkspaceStatusRead:
    """Archive the workspace (AC-8)."""
    if not await is_workspace_owner(session, auth.user.id, workspace_id):
        raise HTTPException(
            status_code=403, detail="Only workspace owner can archive the workspace"
        )
    svc = GovernanceService(session)
    return await svc.archive_workspace(
        workspace_id, actor_id=auth.user.id if auth.user else None
    )


@router.post("/restore", response_model=WorkspaceStatusRead)
async def restore_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.SETTINGS_UPDATE.value,
            "You don't have permission to restore this workspace",
        )
    ),
) -> WorkspaceStatusRead:
    """Restore an archived workspace (AC-8)."""
    if not await is_workspace_owner(session, auth.user.id, workspace_id):
        raise HTTPException(
            status_code=403, detail="Only workspace owner can restore the workspace"
        )
    svc = GovernanceService(session)
    return await svc.restore_workspace(
        workspace_id, actor_id=auth.user.id if auth.user else None
    )
