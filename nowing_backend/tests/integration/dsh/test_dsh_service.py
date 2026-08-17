from __future__ import annotations

import pytest

from app.db import DshMissionStatus
from app.services.dsh_mission_service import DshMissionService

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_create_mission_sets_defaults(db_session, db_workspace, db_user):
    """Pattern 6: creating a row stores payload and a starter checkpoint."""
    service = DshMissionService()
    mission = await service.create_mission(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload={"query": "bds"},
    )
    assert mission.workspace_id == db_workspace.id
    assert mission.user_id == db_user.id
    assert mission.status == DshMissionStatus.PENDING.value
    assert mission.checkpoint == {"phase": "crawl", "subtasks": []}
    assert mission.payload == {"query": "bds"}


@pytest.mark.asyncio
async def test_update_checkpoint_clamps_progress(db_session, db_workspace, db_user):
    """Pattern 4: progress_percent is clamped to [0, 100]."""
    service = DshMissionService()
    mission = await service.create_mission(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        payload={},
    )
    await service.update_checkpoint(
        db_session,
        mission,
        progress_percent=5000,
        status="running",
    )
    assert mission.progress_percent == 100
    assert mission.status == DshMissionStatus.RUNNING.value
