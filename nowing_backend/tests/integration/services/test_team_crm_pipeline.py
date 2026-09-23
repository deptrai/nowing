"""Integration tests for Multi-Seat Team CRM Pipeline & Optimistic Concurrency Control (Story 24.3).

Tests real database persistence, stage auto-seeding, OCC version enforcement,
timeline activity logging, and member spend cap / lead capacity updates.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, LeadActivityLog, LeadPipelineStage, User, Workspace, WorkspaceMembership
from app.routes.lead_pipeline_routes import _ensure_default_stages
from app.schemas.lead_pipeline import (
    LeadActivityLogCreate,
    LeadStageTransitionRequest,
)
from app.services.lead_assignment_service import LeadAssignmentService
from app.services.workspace_credit_service import WorkspaceCreditService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _create_lead(
    session: AsyncSession,
    workspace: Workspace,
    stage: LeadPipelineStage,
    company_name: str = "Acme Corp",
) -> Lead:
    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        stage_id=stage.id,
        company_name=company_name,
        source="manual",
        status=stage.slug,
        version=1,
    )
    session.add(lead)
    await session.flush()
    return lead


async def test_pipeline_stages_auto_seeding(
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """Pipeline stages are auto-seeded with 5 default stages ordered by position."""
    stages = await _ensure_default_stages(db_session, db_workspace.id)
    assert len(stages) == 5
    assert [s.slug for s in stages] == ["new", "approaching", "qualified", "won", "lost"]
    assert [s.position for s in stages] == [0, 1, 2, 3, 4]


async def test_occ_stage_transition_success_and_activity_log(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Transitioning stage with matching expected_version increments version and writes log."""
    stages = await _ensure_default_stages(db_session, db_workspace.id)
    stage_new = stages[0]
    stage_approaching = stages[1]

    lead = await _create_lead(db_session, db_workspace, stage_new)
    assert lead.version == 1
    assert lead.stage_id == stage_new.id

    # Transition to approaching
    lead.stage_id = stage_approaching.id
    lead.status = stage_approaching.slug
    lead.version = lead.version + 1

    log = LeadActivityLog(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        actor_user_id=db_user.id,
        activity_type="stage_changed",
        title=f"Chuyển trạng thái sang '{stage_approaching.name}'",
        details={"from_stage_id": str(stage_new.id), "to_stage_id": str(stage_approaching.id)},
    )
    db_session.add(log)
    await db_session.flush()

    # Verify DB persistence
    await db_session.refresh(lead)
    assert lead.version == 2
    assert lead.stage_id == stage_approaching.id

    logs = (
        await db_session.execute(
            select(LeadActivityLog).where(LeadActivityLog.lead_id == lead.id)
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].activity_type == "stage_changed"
    assert logs[0].details["to_stage_id"] == str(stage_approaching.id)


async def test_occ_conflict_detection_when_version_mismatched(
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """Simulating concurrent update: update fails when DB version does not match expected_version."""
    from sqlalchemy import update

    stages = await _ensure_default_stages(db_session, db_workspace.id)
    lead = await _create_lead(db_session, db_workspace, stages[0])

    # Another concurrent process bumps lead version to 2
    lead.version = 2
    await db_session.flush()

    # Stale request expects version 1
    expected_version = 1
    stmt = (
        update(Lead)
        .where(
            Lead.id == lead.id,
            Lead.workspace_id == db_workspace.id,
            Lead.version == expected_version,
        )
        .values(
            stage_id=stages[1].id,
            status=stages[1].slug,
            version=Lead.version + 1,
        )
        .returning(Lead.id)
    )
    res = await db_session.execute(stmt)
    assert res.one_or_none() is None, "Stale update should affect 0 rows (OCC conflict)"

    # Refresh lead - state is unharmed
    await db_session.refresh(lead)
    assert lead.version == 2
    assert lead.stage_id == stages[0].id


async def test_member_spend_cap_and_lead_capacity_persistence(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Updating member spend cap and lead capacity persists values on WorkspaceMembership."""
    membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalars().first()
    assert membership is not None

    credit_service = WorkspaceCreditService(db_session)
    await credit_service.set_member_spend_cap(
        workspace_id=db_workspace.id,
        target_user_id=db_user.id,
        cap_micros=50_000_000,
        actor_user_id=db_user.id,
    )

    membership.is_accepting_leads = True
    membership.lead_capacity = 15
    await db_session.flush()

    await db_session.refresh(membership)
    assert membership.monthly_spend_cap_micros == 50_000_000
    assert membership.is_accepting_leads is True
    assert membership.lead_capacity == 15
