"""FastAPI routes for Multi-Seat Team CRM Pipeline, OCC Stage Transitions & Timeline (Story 24.3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    Lead,
    LeadActivityLog,
    LeadPipelineStage,
    Permission,
    WorkspaceMembership,
    get_async_session,
    has_permission,
)
from app.redis_client import get_redis_client
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
from app.services.lead_assignment_service import (
    LeadAssignmentService,
    NoEligibleAssigneeError,
)
from app.services.workspace_credit_service import WorkspaceCreditService
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access, is_workspace_owner

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


def _can_view_all_leads(membership: WorkspaceMembership) -> bool:
    """Return True for owners and members with lead-management permissions."""
    if membership.is_owner:
        return True
    if membership.role and membership.role.permissions:
        perms = membership.role.permissions
        return has_permission(perms, Permission.LEADS_WRITE.value) or has_permission(
            perms, Permission.CRM_WRITE.value
        )
    return False


def _lead_visibility_filter(user_id: Any, membership: WorkspaceMembership) -> Any:
    """Return a Lead filter clause that restricts non-admin members to assigned leads."""
    if _can_view_all_leads(membership):
        return True
    return Lead.assigned_to_user_id == user_id


async def _require_lead_visible(
    session: AsyncSession,
    workspace_id: int,
    lead_id: UUID,
    membership: WorkspaceMembership,
) -> Lead:
    """Fetch a lead and fail closed if the caller may not view it."""
    lead = await session.get(Lead, (lead_id, workspace_id))
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found in workspace {workspace_id}",
        )
    user_id = membership.user_id
    if not _can_view_all_leads(membership) and lead.assigned_to_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found in workspace {workspace_id}",
        )
    return lead


async def _set_lead_tenant_context(
    session: AsyncSession,
    workspace_id: int,
    membership: WorkspaceMembership,
) -> None:
    """Set RLS GUCs including the calling user's lead visibility."""
    user_id = str(membership.user_id) if membership and membership.user_id else None
    is_lead_admin = "true" if _can_view_all_leads(membership) else "false"
    await set_request_tenant_context(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        is_lead_admin=is_lead_admin,
    )


async def _ensure_default_stages(
    session: AsyncSession, workspace_id: int
) -> list[LeadPipelineStage]:
    """Auto-seed default pipeline stages if workspace has none configured."""
    stmt = (
        select(LeadPipelineStage)
        .where(LeadPipelineStage.workspace_id == workspace_id)
        .order_by(LeadPipelineStage.position)
    )
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
        try:
            await session.commit()
            await set_request_tenant_context(session, workspace_id=workspace_id)
            for s in stages:
                await session.refresh(s)
        except IntegrityError:
            # Concurrent request created the same default stages; rollback and re-query.
            await session.rollback()
            await set_request_tenant_context(session, workspace_id=workspace_id)
            res = await session.execute(stmt)
            stages = list(res.scalars().all())

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
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)
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
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)

    existing = await session.execute(
        select(LeadPipelineStage).where(
            LeadPipelineStage.workspace_id == workspace_id,
            LeadPipelineStage.slug == payload.slug,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stage slug '{payload.slug}' already exists in this workspace",
        )

    stage = LeadPipelineStage(
        workspace_id=workspace_id,
        name=payload.name,
        slug=payload.slug,
        position=payload.position,
        color=payload.color,
        is_system=payload.is_system,
    )
    session.add(stage)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stage slug '{payload.slug}' already exists in this workspace",
        ) from None
    await _set_lead_tenant_context(session, workspace_id, membership)
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
) -> LeadStageTransitionResponse | JSONResponse:
    """Move lead across Kanban stages with Optimistic Concurrency Control (OCC).

    Returns 409 Conflict if expected_version does not match current DB version.
    """
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)

    # Fetch stage first (no update if invalid)
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

    # Verify the lead is visible to the caller before allowing any transition.
    await _require_lead_visible(session, workspace_id, lead_id, membership)

    # Atomic OCC update: version must match exactly
    prev_version = payload.expected_version
    update_stmt = (
        update(Lead)
        .where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
            Lead.version == payload.expected_version,
        )
        .values(
            stage_id=payload.stage_id,
            status=stage.slug,
            version=Lead.version + 1,
        )
        .returning(Lead.id, Lead.workspace_id, Lead.stage_id, Lead.version, Lead.status)
    )
    res = await session.execute(update_stmt)
    row = res.one_or_none()
    if row is None:
        # Conflict: fetch current version/stage for 409 body
        current = await session.execute(
            select(Lead.id, Lead.version, Lead.stage_id, Lead.assigned_to_user_id).where(
                Lead.id == lead_id,
                Lead.workspace_id == workspace_id,
            )
        )
        current_row = current.one_or_none()
        if current_row is None:
            # Lead does not exist at all: return 404, not 409.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead {lead_id} not found in workspace {workspace_id}",
            ) from None
        current_version, current_stage_id = current_row[1], current_row[2]
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": (
                    f"Lead was modified by another member (DB version: {current_version}, "
                    f"expected: {payload.expected_version})."
                ),
                "error_code": "concurrency_conflict",
                "current_version": current_version,
                "current_stage_id": str(current_stage_id) if current_stage_id else None,
            },
        )

    _, _, stage_id, version, lead_status = row

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
            "version": version,
            "note": payload.note,
        },
    )
    session.add(log)
    await session.commit()

    return LeadStageTransitionResponse(
        lead_id=lead_id,
        workspace_id=workspace_id,
        stage_id=stage_id,
        version=version,
        previous_version=prev_version,
        status=lead_status,
    )


@router.get(
    "/{lead_id}/timeline",
    response_model=list[LeadActivityLogRead],
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
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)

    await _require_lead_visible(session, workspace_id, lead_id, membership)

    stmt = (
        select(LeadActivityLog)
        .where(
            LeadActivityLog.workspace_id == workspace_id,
            LeadActivityLog.lead_id == lead_id,
        )
        .order_by(LeadActivityLog.created_at.asc())
    )
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
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)

    await _require_lead_visible(session, workspace_id, lead_id, membership)

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
    await _set_lead_tenant_context(session, workspace_id, membership)
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
    redis_client: Any = Depends(get_redis_client),
) -> dict[str, Any]:
    """Manually assign or reassign lead to a designated member."""
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)

    await _require_lead_visible(session, workspace_id, lead_id, membership)

    svc = LeadAssignmentService(session=session, redis_client=redis_client)
    try:
        result = await svc.reassign_lead(
            workspace_id=workspace_id,
            lead_id=lead_id,
            target_user_id=payload.target_user_id,
            actor_user_id=auth.user.id if auth and auth.user else None,
            reason=payload.reason or "manual_reassignment",
        )
    except NoEligibleAssigneeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.reason,
        ) from exc
    await session.commit()
    return {
        "lead_id": str(result.lead_id),
        "workspace_id": result.workspace_id,
        "assigned_to_user_id": str(result.assigned_to_user_id)
        if result.assigned_to_user_id
        else None,
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
    redis_client: Any = Depends(get_redis_client),
) -> dict[str, Any]:
    """Batch round-robin distribution of newly imported leads."""
    if not payload.lead_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lead_ids must not be empty",
        )
    if len(payload.lead_ids) != len(set(payload.lead_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lead_ids contains duplicates",
        )

    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)

    # Validate every requested lead exists in the workspace.
    existing_stmt = select(Lead.id).where(
        Lead.workspace_id == workspace_id,
        Lead.id.in_(payload.lead_ids),
    )
    existing_res = await session.execute(existing_stmt)
    existing_ids = set(existing_res.scalars().all())
    missing = [lid for lid in payload.lead_ids if lid not in existing_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lead IDs not found in workspace: {[str(lead_id) for lead_id in missing]}",
        )

    svc = LeadAssignmentService(session=session, redis_client=redis_client)
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
                "assigned_to_user_id": str(a.assigned_to_user_id)
                if a.assigned_to_user_id
                else None,
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

    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)

    svc = WorkspaceCreditService(session=session)
    try:
        status_obj = await svc.get_member_spend_status(
            workspace_id=workspace_id,
            user_id=auth.user.id if auth and auth.user else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
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
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)
    if not await is_workspace_owner(session, auth.user.id, workspace_id):
        raise HTTPException(
            status_code=403, detail="Only workspace owner can set spend cap"
        )

    svc = WorkspaceCreditService(session=session)
    try:
        await svc.set_member_spend_cap(
            workspace_id=workspace_id,
            target_user_id=target_user_id,
            cap_micros=payload.monthly_spend_cap_micros,
            actor_user_id=auth.user.id if auth and auth.user else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
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
    membership = await check_workspace_access(session, auth, workspace_id)
    await _set_lead_tenant_context(session, workspace_id, membership)
    if not await is_workspace_owner(session, auth.user.id, workspace_id):
        raise HTTPException(
            status_code=403, detail="Only workspace owner can set member capacity"
        )

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
