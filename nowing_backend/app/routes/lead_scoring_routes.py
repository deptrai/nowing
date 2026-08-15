"""REST routes for lead scoring and prioritization (Story 21.2)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    LeadScore,
    Permission,
    Workspace,
    get_async_session,
)
from app.lead_intelligence.scoring.schemas import (
    IcpCriteria,
    LeadScoreInput,
    LeadScoreOutput,
    LeadScoreRead,
)
from app.lead_intelligence.scoring.service import LeadScoringService
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/leads/score",
    response_model=LeadScoreOutput,
    status_code=status.HTTP_200_OK,
)
async def score_leads(
    workspace_id: int,
    body: LeadScoreInput,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> LeadScoreOutput:
    """Trigger lead scoring for a list of leads or all leads in the workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_SCORE.value,
        error_message="You don't have permission to score leads in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    client_id = auth.pat.client_id if auth.pat is not None else None
    ctx = SimpleNamespace(
        session=session,
        workspace_id=workspace_id,
        run_id=None,
        client_id=client_id,
        user_id=auth.user.id,
    )
    service = LeadScoringService()
    return await service.score(session, ctx, body)


@router.get(
    "/workspaces/{workspace_id}/leads/scores",
    response_model=list[LeadScoreRead],
)
async def list_lead_scores(
    workspace_id: int,
    lead_id: UUID | None = None,
    company_name: str | None = None,
    classification: str | None = None,
    min_score: float | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    sort: str = Query(default="-computed_at"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[LeadScoreRead]:
    """List lead scores with optional filters and pagination."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view lead scores in this workspace",
    )

    stmt = select(LeadScore).where(LeadScore.workspace_id == workspace_id)
    if lead_id is not None:
        stmt = stmt.where(LeadScore.lead_id == lead_id)
    if company_name is not None:
        stmt = stmt.where(LeadScore.company_name.ilike(f"%{company_name}%"))
    if classification is not None:
        stmt = stmt.where(LeadScore.classification == classification)
    if min_score is not None:
        stmt = stmt.where(LeadScore.score >= min_score)
    if from_date is not None:
        stmt = stmt.where(LeadScore.computed_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(LeadScore.computed_at <= to_date)

    if sort == "-score":
        stmt = stmt.order_by(desc(LeadScore.score), desc(LeadScore.computed_at))
    elif sort == "score":
        stmt = stmt.order_by(LeadScore.score, desc(LeadScore.computed_at))
    else:
        stmt = stmt.order_by(desc(LeadScore.computed_at))

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return [
        LeadScoreRead.model_validate(row, from_attributes=True)
        for row in result.scalars().all()
    ]


@router.get(
    "/workspaces/{workspace_id}/leads/{lead_id}/score",
    response_model=LeadScoreRead,
)
async def get_latest_lead_score(
    workspace_id: int,
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> LeadScoreRead:
    """Return the most recent score for a single lead."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view lead scores in this workspace",
    )

    stmt = (
        select(LeadScore)
        .where(
            LeadScore.workspace_id == workspace_id,
            LeadScore.lead_id == lead_id,
        )
        .order_by(desc(LeadScore.computed_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No lead score found",
        )
    return LeadScoreRead.model_validate(row, from_attributes=True)


@router.get(
    "/workspaces/{workspace_id}/leads/{lead_id}/score/history",
    response_model=list[LeadScoreRead],
)
async def get_lead_score_history(
    workspace_id: int,
    lead_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[LeadScoreRead]:
    """Return historical scores for a single lead."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view lead scores in this workspace",
    )

    stmt = (
        select(LeadScore)
        .where(
            LeadScore.workspace_id == workspace_id,
            LeadScore.lead_id == lead_id,
        )
        .order_by(desc(LeadScore.computed_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [
        LeadScoreRead.model_validate(row, from_attributes=True)
        for row in result.scalars().all()
    ]


@router.put(
    "/workspaces/{workspace_id}/icp",
    response_model=IcpCriteria,
)
async def update_icp_criteria(
    workspace_id: int,
    body: IcpCriteria,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> IcpCriteria:
    """Update the Ideal Customer Profile criteria for a workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.SETTINGS_UPDATE.value,
        error_message="You don't have permission to update workspace settings",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    workspace.icp_criteria = body.model_dump()
    session.add(workspace)
    await session.commit()

    return body
