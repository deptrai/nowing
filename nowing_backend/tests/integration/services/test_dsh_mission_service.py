"""Pattern 6 integration tests for DshMissionService (Story 26.5).

These tests run the real DshMissionService against a real Postgres database
through the transactional ``db_session`` fixture. They assert workspace-scoped
queries, 404 behaviour, and checkpoint persistence.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db import DshMission, DshMissionStatus, User, Workspace
from app.services.dsh_mission_service import (
    DshMissionService,
    DshMissionServiceError,
)

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_create_mission_persists_initial_state(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: create_mission inserts a pending mission with a default checkpoint."""
    svc = DshMissionService()
    payload = {"query": "unlock shimmer test"}

    mission = await svc.create_mission(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload=payload,
    )

    assert mission.workspace_id == db_workspace.id
    assert mission.user_id == db_user.id
    assert mission.mission_type == "deep_lead_research"
    assert mission.status == DshMissionStatus.PENDING.value
    assert mission.phase == "crawl"
    assert mission.progress_percent == 0
    assert mission.payload == payload
    assert mission.checkpoint == {
        "version": 1,
        "phase": "crawl",
        "subtasks": [],
    }

    row = await db_session.get(DshMission, mission.id)
    assert row is not None
    assert row.workspace_id == db_workspace.id
    assert row.status == "pending"
    assert row.checkpoint["version"] == 1


@pytest.mark.asyncio
async def test_get_mission_for_workspace_returns_scoped_mission(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: get_mission_for_workspace returns the mission when scoped to the workspace."""
    svc = DshMissionService()
    mission = await svc.create_mission(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload={"query": "x"},
    )

    found = await svc.get_mission_for_workspace(db_session, mission.id, db_workspace.id)

    assert found.id == mission.id
    assert found.workspace_id == db_workspace.id


@pytest.mark.asyncio
async def test_get_mission_for_workspace_raises_for_missing_mission(
    db_session, db_workspace: Workspace
) -> None:
    """P0: get_mission_for_workspace raises when the mission id does not exist."""
    svc = DshMissionService()

    with pytest.raises(DshMissionServiceError, match="Mission not found"):
        await svc.get_mission_for_workspace(db_session, uuid4(), db_workspace.id)


@pytest.mark.asyncio
async def test_get_mission_for_workspace_raises_for_other_workspace(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: get_mission_for_workspace rejects a mission that belongs to another workspace."""
    other_workspace = Workspace(name="Other Test Space", user_id=db_user.id)
    db_session.add(other_workspace)
    await db_session.flush()

    svc = DshMissionService()
    other_mission = await svc.create_mission(
        db_session,
        workspace_id=other_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload={"query": "other"},
    )

    with pytest.raises(DshMissionServiceError, match="Mission not found"):
        await svc.get_mission_for_workspace(
            db_session, other_mission.id, db_workspace.id
        )


@pytest.mark.asyncio
async def test_get_mission_or_404_returns_mission(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: get_mission_or_404 loads a mission by id."""
    svc = DshMissionService()
    mission = await svc.create_mission(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload={"query": "y"},
    )

    found = await svc.get_mission_or_404(db_session, mission.id)

    assert found.id == mission.id
    assert found.workspace_id == db_workspace.id


@pytest.mark.asyncio
async def test_get_mission_or_404_raises_for_missing_mission(
    db_session,
) -> None:
    """P0: get_mission_or_404 raises when the mission id does not exist."""
    svc = DshMissionService()

    with pytest.raises(DshMissionServiceError, match="Mission not found"):
        await svc.get_mission_or_404(db_session, uuid4())


@pytest.mark.asyncio
async def test_update_checkpoint_persists_state(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P0: update_checkpoint writes phase, progress, status, and checkpoint."""
    svc = DshMissionService()
    mission = await svc.create_mission(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload={"query": "z"},
    )

    checkpoint = {
        "version": 1,
        "phase": "crawl",
        "subtasks": [
            {
                "id": "subtask-1",
                "title": "Crawl",
                "status": "success",
                "phase": "crawl",
                "tokens_used": 1200,
                "tokens_per_second": 60.0,
                "cost_micros": 5000,
            },
            {
                "id": "subtask-2",
                "title": "Reasoning",
                "status": "running",
                "phase": "reasoning",
                "tokens_used": 3000,
                "tokens_per_second": 120.0,
                "cost_micros": 10000,
            },
        ],
    }

    updated = await svc.update_checkpoint(
        db_session,
        mission,
        checkpoint=checkpoint,
        phase="reasoning",
        progress_percent=45,
        current_subtask_id="subtask-2",
        status="running",
    )

    assert updated.id == mission.id
    assert updated.status == "running"
    assert updated.phase == "reasoning"
    assert updated.progress_percent == 45
    assert updated.current_subtask_id == "subtask-2"
    assert updated.checkpoint["version"] == 2
    assert updated.checkpoint["phase"] == "crawl"
    assert updated.checkpoint["subtasks"][0]["id"] == "subtask-1"

    row = await db_session.get(DshMission, mission.id)
    assert row is not None
    assert row.status == "running"
    assert row.phase == "reasoning"
    assert row.progress_percent == 45
    assert row.current_subtask_id == "subtask-2"
    assert row.checkpoint["version"] == 2


@pytest.mark.asyncio
async def test_update_checkpoint_rejects_stale_version(
    db_session, db_user: User, db_workspace: Workspace
) -> None:
    """P1: update_checkpoint raises when the supplied checkpoint version is stale."""
    svc = DshMissionService()
    mission = await svc.create_mission(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload={"query": "stale"},
    )

    with pytest.raises(DshMissionServiceError, match="Stale checkpoint version"):
        await svc.update_checkpoint(
            db_session,
            mission,
            checkpoint={"version": 0, "subtasks": []},
        )

    row = await db_session.get(DshMission, mission.id)
    assert row is not None
    assert row.status == "pending"
    assert row.phase == "crawl"
    assert row.checkpoint["version"] == 1
