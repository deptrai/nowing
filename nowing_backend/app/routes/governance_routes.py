"""Governance console routes (Story 29.6 / FR-97).

Prefix: /workspaces/{workspace_id}/governance
Guards: workspace-scoped RBAC permissions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, get_async_session
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
from app.services.governance_service import GovernanceService
from app.users import get_auth_context
from app.utils.rbac import check_permission, is_workspace_owner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/governance", tags=["governance"])


@router.get("", response_model=GovernanceOverviewRead)
async def get_governance_overview(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> GovernanceOverviewRead:
    """Return combined governance console payload (AC-1)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_VIEW.value,
        "You don't have permission to view governance settings",
    )
    svc = GovernanceService(session)
    return await svc.get_overview(workspace_id)


@router.put("/retention", response_model=RetentionPolicyRead)
async def update_retention_policy(
    workspace_id: int,
    payload: RetentionPolicyUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> RetentionPolicyRead:
    """Update workspace retention policy (AC-2/AC-3)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to update governance settings",
    )
    svc = GovernanceService(session)
    return await svc.update_retention_policy(
        workspace_id, payload, actor_id=auth.user.id if auth.user else None
    )


@router.get("/source-risk-tiers", response_model=list[SourceRiskTierRead])
async def list_source_risk_tiers(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[SourceRiskTierRead]:
    """List configured source risk tiers (AC-3)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_VIEW.value,
        "You don't have permission to view governance settings",
    )
    svc = GovernanceService(session)
    return await svc.list_source_risk_tiers()


@router.put("/source-risk-tiers", response_model=SourceRiskTierRead)
async def upsert_source_risk_tier(
    workspace_id: int,
    payload: SourceRiskTierUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SourceRiskTierRead:
    """Create or update a source risk tier; pause scraping on high risk (AC-5)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to update governance settings",
    )
    svc = GovernanceService(session)
    return await svc.upsert_source_risk_tier(
        payload, actor_id=auth.user.id if auth.user else None
    )


@router.get("/dnc-records", response_model=list[DncRecordRead])
async def list_dnc_records(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[DncRecordRead]:
    """List workspace DNC records with global supersession flags (AC-6)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_VIEW.value,
        "You don't have permission to view governance settings",
    )
    svc = GovernanceService(session)
    return await svc.list_dnc_records(workspace_id)


@router.post("/dnc-records", response_model=DncRecordRead, status_code=201)
async def create_dnc_record(
    workspace_id: int,
    payload: DncRecordCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DncRecordRead:
    """Create a workspace DNC record (AC-6)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to update governance settings",
    )
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
) -> None:
    """Delete a workspace DNC record (AC-6)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to update governance settings",
    )
    svc = GovernanceService(session)
    await svc.delete_dnc_record(
        workspace_id, record_id, actor_id=auth.user.id if auth.user else None
    )


@router.post("/right-to-delete", response_model=RightToDeleteResponse)
async def right_to_delete(
    workspace_id: int,
    payload: RightToDeleteRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> RightToDeleteResponse:
    """Right-to-delete single or bulk memory (AC-4)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_DELETE.value,
        "You don't have permission to delete memories",
    )
    svc = GovernanceService(session)
    return await svc.right_to_delete(
        workspace_id, payload, actor_id=auth.user.id if auth.user else None
    )


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
) -> list[AuditLogRead]:
    """Query governance audit events for the workspace (AC-7)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_VIEW.value,
        "You don't have permission to view governance settings",
    )
    from datetime import datetime

    filters = AuditLogFilter(
        action_prefix=action_prefix,
        created_after=datetime.fromisoformat(created_after) if created_after else None,
        created_before=datetime.fromisoformat(created_before) if created_before else None,
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
) -> WorkspaceStatusRead:
    """Archive the workspace (AC-8)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to archive this workspace",
    )
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
) -> WorkspaceStatusRead:
    """Restore an archived workspace (AC-8)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to restore this workspace",
    )
    if not await is_workspace_owner(session, auth.user.id, workspace_id):
        raise HTTPException(
            status_code=403, detail="Only workspace owner can restore the workspace"
        )
    svc = GovernanceService(session)
    return await svc.restore_workspace(
        workspace_id, actor_id=auth.user.id if auth.user else None
    )
