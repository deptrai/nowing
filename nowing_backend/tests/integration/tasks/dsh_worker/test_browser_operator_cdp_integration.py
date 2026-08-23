import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db import DshMission, User, Workspace
from app.redis_client import get_redis_client
from app.routes.dsh_routes import pause_mission, resume_mission

pytestmark = [pytest.mark.integration]


async def _create_test_workspace_and_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4()}@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    workspace = Workspace(
        name="Test Workspace",
        user_id=user.id,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(workspace)
    return user, workspace


@pytest.mark.asyncio
async def test_pause_status_update(db_session):
    """should execute pause_mission route and set mission phase to waiting_for_human."""
    user, workspace = await _create_test_workspace_and_user(db_session)
    mission = DshMission(user_id=user.id, workspace_id=workspace.id, status="running", phase="waiting_for_human")
    db_session.add(mission)
    await db_session.commit()
    await db_session.refresh(mission)

    auth_mock = MagicMock()
    auth_mock.user.id = user.id
    auth_mock.method = "session"

    response = await pause_mission(mission.id, auth_mock, db_session)

    assert response["phase"] == "waiting_for_human"
    await db_session.refresh(mission)
    assert mission.phase == "waiting_for_human"
    assert mission.current_subtask_id == "cdp_crawl"

    redis = await get_redis_client()
    takeover_key = f"dsh:lock:takeover:{workspace.id}:{mission.id}"
    assert await redis.get(takeover_key)
    await redis.delete(takeover_key)


@pytest.mark.asyncio
async def test_resume_cas_update(db_session):
    """should execute resume_mission route with atomic CAS and transition waiting_for_human -> crawl."""
    user, workspace = await _create_test_workspace_and_user(db_session)
    mission = DshMission(user_id=user.id, workspace_id=workspace.id, status="running", phase="waiting_for_human")
    db_session.add(mission)
    await db_session.commit()
    await db_session.refresh(mission)

    auth_mock = MagicMock()
    auth_mock.user.id = user.id
    auth_mock.method = "session"

    redis = await get_redis_client()
    takeover_key = f"dsh:lock:takeover:{workspace.id}:{mission.id}"
    await redis.setex(takeover_key, 900, str(user.id))

    with patch("app.services.dsh_mission_service.DshMissionService.publish_to_stream", new_callable=AsyncMock):
        response = await resume_mission(mission.id, auth_mock, db_session)
        assert response["phase"] == "crawl"

    await db_session.refresh(mission)
    assert mission.phase == "crawl"
    assert await redis.get(takeover_key) is None


@pytest.mark.asyncio
async def test_resume_cas_conflict(db_session):
    """should return 409 Conflict when attempting to resume a mission that is not waiting_for_human."""
    user, workspace = await _create_test_workspace_and_user(db_session)
    mission = DshMission(user_id=user.id, workspace_id=workspace.id, status="running", phase="crawl")
    db_session.add(mission)
    await db_session.commit()
    await db_session.refresh(mission)

    auth_mock = MagicMock()
    auth_mock.user.id = user.id
    auth_mock.method = "session"

    with pytest.raises(HTTPException) as exc_info:
        await resume_mission(mission.id, auth_mock, db_session)

    assert exc_info.value.status_code == 409
