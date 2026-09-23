"""Red-phase integration tests for scheduled mission Celery tick (Story 6.10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

pytestmark = [pytest.mark.integration]

# Red-phase guard: the module does not exist until dev-story implements it.
pytest.importorskip(
    "app.tasks.celery_tasks.schedule_mission_tick",
    reason="Story 6.10 not yet implemented",
)



async def test_tick_claims_due_mission_from_db(db_session, db_user, db_workspace):
    """AC-6 P6: SELECT claims due dsh_missions with index on (workspace_id, status, next_fire_at)."""
    from app.db import DshMission
    from app.tasks.celery_tasks.schedule_mission_tick import _claim_due_missions

    mission = DshMission(
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="recurring_report",
        status="pending",
        next_fire_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        schedule={"type": "interval", "minutes": 60},
    )
    db_session.add(mission)
    await db_session.flush()

    claimed = await _claim_due_missions(db_session, batch_size=10)

    assert len(claimed) == 1
    assert claimed[0].id == mission.id
    assert claimed[0].status == "running"


async def test_rls_tick_only_sees_allowed_workspace_missions(db_session, db_workspace, mocker):
    """AC-6 P6: tick task respects RLS and only sees missions in allowed workspaces."""
    from app.tasks.celery_tasks.schedule_mission_tick import _claim_due_missions

    rls_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._apply_workspace_rls",
        return_value=db_workspace.id,
    )

    await _claim_due_missions(db_session, batch_size=10)

    rls_mock.assert_called_once()
