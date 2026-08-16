"""FastAPI routes for Multi-Seat Team CRM Pipeline, OCC Stage Transitions & Timeline (Story 24.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.canonical.tenant_context import set_request_tenant_context
from app.db import (
    Lead,
    LeadActivityLog,
    LeadPipelineStage,
    WorkspaceMembership,
    get_async_session,
)
from app.schemas.lead_pipeline import (
    BatchLeadAssignmentRequest,
    LeadActivityLogCreate,
    LeadActivityLogRead,
    LeadAssignmentRequest,
    LeadPipelineStageCreate,
    LeadPipelineStageRead,
    LeadStageTransitionRequest,
    LeadStageTransitionResponse,
    MemberLeadCapacityUpdateRequest,
    MemberSpendCapUpdateRequest,
)
from app.services.lead_assignment_service import LeadAssignmentService
from app.services.workspace_credit_service import WorkspaceCreditService
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access, check_permission

router = APIRouter(
    prefix="/workspaces/{workspace_id}/leads",
    tags=["lead-pipeline"],
)

DEFAULT_STAGES = [
    {"name": "Mới săn", "slug": "new", "position": 0, "color": "#3B82F6"},
    {"name": "Đang tiếp cận", "slug": "approaching", "position": 1, "color": "#EAB308"},
    {"name": "Tiềm năng", "slug": "qualified", "position": 2, "color": "#8B5CF6"},
    {"name": "Đã chốt", "slug": "won", "position": 3, "color": "#10B981"},
    {"name": "Hủy / Không nhu cầu", "slug": "lost", "position": 4, "color": "#EF4444"},
]


async def _ensure_default_stages(
    session: AsyncSession, workspace_id: int
) -> list[LeadPipelineStage]:
    """Auto-seed default pipeline stages if workspace has none configured."""
    stmt = select(LeadPipelineStage).where(
        LeadPipelineStage.workspace_id == workspace_id
    ).order_by(LeadPipelineStage.position)
    res = await session.execute(stmt)
    stages = list(res.scalars().all())

    if not stages:
        for stage_def in DEFAULT_STAGES:
            new_stage = LeadPipelineStage(
                workspace_id=workspace_id,
                name=stage_def["name"],
                slug=stage_def["slug"],
                position=stage_def["position"],
                color=stage_def["color"],
                is_system=True,
            )
            session.add(new_stage)
            stages.append(new_stage)
        await session.commit()
        for s in stages:
            await session.refresh(s)

    return stages


@router.get(
    "/pipeline/stages",
    response_model=list[LeadPipelineStageRead],
)
async def list_pipeline_stages(
    workspace_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[LeadPipelineStage]:
    """Retrieve Kanban pipeline stages ordered by position."""
    await set_request_tenant_context(session, workspace_id=workspace_id)
    stages = await _ensure_default_stages(session, workspace_id)
    return stages


@router.post(
    "/pipeline/stages",
    response_model=LeadPipelineStageRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pipeline_stage(
    workspace_id: int,
    payload: LeadPipelineStageCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> LeadPipelineStage:
    """Create a custom Kanban stage for the workspace."""
    await set_request_tenant_context(session, workspace_id=workspace_id)

    stage = LeadPipelineStage(
        workspace_id=workspace_id,
        name=payload.name,
        slug=payload.slug,
        position=payload.position,
        color=payload.color,
        is_system=payload.is_system,
    )
    session.add(stage)
    await session.commit()
    await session.refresh(stage)
    return stage


@router.patch(
    "/{lead_id}/stage",
    response_model=LeadStageTransitionResponse,
)
async def transition_lead_stage(
    workspace_id: int,
    lead_id: UUID,
    payload: LeadStageTransitionRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> LeadStageTransitionResponse:
    """Move lead across Kanban stages with Optimistic Concurrency Control (OCC).

    Returns 409 Conflict if expected_version does not match current DB version.
    """
    await set_request_tenant_context(session, workspace_id=workspace_id)

    stmt = select(Lead).where(
        Lead.id == lead_id,
        Lead.workspace_id == workspace_id,
    )
    res = await session.execute(stmt)
    lead = res.scalars().first()

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found in workspace {workspace_id}",
        )

    # OCC check: return 409 Conflict on version mismatch
    current_version = lead.version or 1
    if payload.expected_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "concurrency_conflict",
                "message": f"Lead was modified by another member (DB version: {current_version}, expected: {payload.expected_version}).",
                "current_version": current_version,
                "current_stage_id": str(lead.stage_id) if lead.stage_id else None,
            },
        )

    # Fetch stage
    stage_stmt = select(LeadPipelineStage).where(
        LeadPipelineStage.id == payload.stage_id,
        LeadPipelineStage.workspace_id == workspace_id,
    )
    stage_res = await session.execute(stage_stmt)
    stage = stage_res.scalars().first()
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stage {payload.stage_id} not found in workspace {workspace_id}",
        )

    prev_version = current_version
    lead.stage_id = payload.stage_id
    lead.status = stage.slug
    lead.version = current_version + 1
    lead.updated_at = datetime.now(UTC)

    # Record activity log
    log = LeadActivityLog(
        workspace_id=workspace_id,
        lead_id=lead_id,
        actor_user_id=auth.user.id if auth and auth.user else None,
        activity_type="stage_changed",
        title=f"Chuyển trạng thái sang '{stage.name}'",
        details={
            "to_stage_id": str(payload.stage_id),
            "to_stage_name": stage.name,
            "to_stage_slug": stage.slug,
            "version": lead.version,
            "note": payload.note,
        },
    )
    session.add(log)
    await session.commit()
    await session.refresh(lead)

    return LeadStageTransitionResponse(
        lead_id=lead.id,
        workspace_id=lead.workspace_id,
        stage_id=lead.stage_id,
        version=lead.version,
        previous_version=prev_version,
        status=lead.status,
    )


@router.get(
    "/{lead_id}/activities",
    response_model=list[LeadActivityLogRead],
)
async def list_lead_activities(
    workspace_id: int,
    lead_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[LeadActivityLog]:
    """Chronological timeline of all interactions with the lead."""
    await set_request_tenant_context(session, workspace_id=workspace_id)

    stmt = select(LeadActivityLog).where(
        LeadActivityLog.workspace_id == workspace_id,
        LeadActivityLog.lead_id == lead_id,
    ).order_by(LeadActivityLog.created_at.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


@router.post(
    "/{lead_id}/activities",
    response_model=LeadActivityLogRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead_activity(
    workspace_id: int,
    lead_id: UUID,
    payload: LeadActivityLogCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> LeadActivityLog:
    """Record a manual internal note or interaction log."""
    await set_request_tenant_context(session, workspace_id=workspace_id)

    log = LeadActivityLog(
        workspace_id=workspace_id,
        lead_id=lead_id,
        actor_user_id=auth.user.id if auth and auth.user else None,
        activity_type=payload.activity_type,
        title=payload.title,
        details=payload.details,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@router.post(
    "/{lead_id}/assign",
    response_model=dict[str, Any],
)
async def assign_or_reassign_lead(
    workspace_id: int,
    lead_id: UUID,
    payload: LeadAssignmentRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Manually assign or reassign lead to a designated member."""
    await set_request_tenant_context(session, workspace_id=workspace_id)
    svc = LeadAssignmentService(session=session)
    result = await svc.reassign_lead(
        workspace_id=workspace_id,
        lead_id=lead_id,
        target_user_id=payload.target_user_id,
        actor_user_id=auth.user.id if auth and auth.user else None,
        reason=payload.reason or "manual_reassignment",
    )
    await session.commit()
    return {
        "lead_id": str(result.lead_id),
        "workspace_id": result.workspace_id,
        "assigned_to_user_id": str(result.assigned_to_user_id) if result.assigned_to_user_id else None,
        "assigned_by": result.assigned_by,
        "status": result.status,
    }


@router.post(
    "/assign-batch",
    response_model=dict[str, Any],
)
async def assign_leads_batch(
    workspace_id: int,
    payload: BatchLeadAssignmentRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Batch round-robin distribution of newly imported leads."""
    await set_request_tenant_context(session, workspace_id=workspace_id)
    svc = LeadAssignmentService(session=session)
    result = await svc.assign_leads_batch(
        workspace_id=workspace_id,
        lead_ids=payload.lead_ids,
    )
    await session.commit()
    return {
        "workspace_id": result.workspace_id,
        "total_assigned": result.total_assigned,
        "assignments": [
            {
                "lead_id": str(a.lead_id),
                "assigned_to_user_id": str(a.assigned_to_user_id) if a.assigned_to_user_id else None,
                "status": a.status,
            }
            for a in result.assignments
        ],
        "unassigned_lead_ids": [str(uid) for uid in result.unassigned_lead_ids],
    }


@router.get(
    "/members/spend-status",
    response_model=dict[str, Any],
)
async def get_my_spend_status(
    workspace_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Retrieve calling user's spend cap status in this workspace."""
    if not auth or not auth.user:
        raise HTTPException(status_code=401, detail="Authentication required")

    svc = WorkspaceCreditService(session=session)
    status_obj = await svc.get_member_spend_status(
        workspace_id=workspace_id,
        user_id=auth.user.id if auth and auth.user else None,
    )
    return {
        "workspace_id": status_obj.workspace_id,
        "user_id": str(status_obj.user_id),
        "monthly_spend_cap_micros": status_obj.monthly_spend_cap_micros,
        "monthly_spent_micros": status_obj.monthly_spent_micros,
        "remaining_cap_micros": status_obj.remaining_cap_micros,
        "workspace_balance_micros": status_obj.workspace_balance_micros,
    }


@router.patch(
    "/members/{target_user_id}/spend-cap",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_member_spend_cap(
    workspace_id: int,
    target_user_id: UUID,
    payload: MemberSpendCapUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Owner/Admin sets monthly spend cap for a workspace member."""
    await set_request_tenant_context(session, workspace_id=workspace_id)
    svc = WorkspaceCreditService(session=session)
    await svc.set_member_spend_cap(
        workspace_id=workspace_id,
        target_user_id=target_user_id,
        cap_micros=payload.monthly_spend_cap_micros,
        actor_user_id=auth.user.id if auth and auth.user else None,
    )
    await session.commit()


@router.patch(
    "/members/{target_user_id}/lead-capacity",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_member_lead_capacity(
    workspace_id: int,
    target_user_id: UUID,
    payload: MemberLeadCapacityUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Configure lead acceptance toggle and max capacity for a member."""
    await set_request_tenant_context(session, workspace_id=workspace_id)
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == target_user_id,
    )
    res = await session.execute(stmt)
    membership = res.scalars().first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    membership.is_accepting_leads = payload.is_accepting_leads
    membership.lead_capacity = payload.lead_capacity
    await session.commit()
