from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db import DshMission, DshMissionStatus
from app.routes.dsh_routes import abort_mission, resume_mission, sweep_takeovers
from app.services.dsh_mission_service import (
    DshMissionService,
    DshMissionServiceError,
    abort_takeover_mission,
    sweep_expired_takeovers,
)

pytestmark = [pytest.mark.unit]


class _FakeResult:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.flushed = False
        self.rolled_back = False
        self.missions: dict[uuid.UUID, DshMission] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, DshMission):
            self.missions[obj.id] = obj

    async def get(self, model: type, ident: Any) -> Any | None:
        if model is DshMission:
            return self.missions.get(ident)
        return None

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        return _FakeResult(list(self.missions.values()))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        self.flushed = True


def _create_mission(
    *,
    status: str = "running",
    phase: str = "waiting_for_human",
    workspace_id: int = 1,
    user_id: uuid.UUID | None = None,
    checkpoint: dict[str, Any] | None = None,
    updated_at: datetime | None = None,
) -> DshMission:
    mission_id = uuid.uuid4()
    mission = DshMission(
        id=mission_id,
        workspace_id=workspace_id,
        user_id=user_id or uuid.uuid4(),
        mission_type="deep_lead_research",
        status=status,
        phase=phase,
        progress_percent=50,
        payload={"query": "test"},
        checkpoint=checkpoint or {},
        updated_at=updated_at or datetime.now(UTC),
    )
    return mission


@pytest.mark.asyncio
async def test_sweep_expired_takeovers_times_out_and_cancels():
    """Given an active mission in waiting_for_human where 15 minutes elapsed, sweep marks it cancelled/aborted_timeout and releases Redis lock."""
    session = _FakeSession()
    now = datetime.now(UTC)
    expired_at = (now - timedelta(minutes=1)).isoformat()

    mission = _create_mission(
        checkpoint={
            "version": 1,
            "takeover": {
                "challenge": "recaptcha",
                "expires_at": expired_at,
            },
        }
    )
    session.add(mission)

    redis_mock = AsyncMock()
    with patch("app.services.dsh_mission_service.get_redis_client", return_value=redis_mock):
        swept = await sweep_expired_takeovers(session)

    assert len(swept) == 1
    assert mission.status == DshMissionStatus.CANCELLED.value
    assert mission.phase == "aborted_timeout"
    assert mission.checkpoint["takeover"]["aborted_reason"] == "timeout"
    assert session.flushed is True

    takeover_key = f"dsh:lock:takeover:{mission.workspace_id}:{mission.id}"
    redis_mock.delete.assert_awaited_once_with(takeover_key)


@pytest.mark.asyncio
async def test_sweep_leaves_active_missions_untouched():
    """Active missions with lock alive (< 15m) are untouched by the sweeper, returning 0 swept."""
    session = _FakeSession()
    now = datetime.now(UTC)
    future_expires = (now + timedelta(minutes=10)).isoformat()

    mission = _create_mission(
        checkpoint={
            "version": 1,
            "takeover": {
                "challenge": "recaptcha",
                "expires_at": future_expires,
            },
        }
    )
    session.add(mission)

    redis_mock = AsyncMock()
    with patch("app.services.dsh_mission_service.get_redis_client", return_value=redis_mock):
        swept = await sweep_expired_takeovers(session)

    assert len(swept) == 0
    assert mission.status == "running"
    assert mission.phase == "waiting_for_human"
    redis_mock.delete.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_fallback_to_updated_at():
    """When expires_at is not in checkpoint, sweeper falls back to updated_at + 15m."""
    session = _FakeSession()
    old_time = datetime.now(UTC) - timedelta(minutes=20)
    mission = _create_mission(
        checkpoint={"version": 1},
        updated_at=old_time,
    )
    session.add(mission)

    redis_mock = AsyncMock()
    with patch("app.services.dsh_mission_service.get_redis_client", return_value=redis_mock):
        swept = await sweep_expired_takeovers(session)

    assert len(swept) == 1
    assert mission.status == DshMissionStatus.CANCELLED.value
    assert mission.phase == "aborted_timeout"


@pytest.mark.asyncio
async def test_abort_takeover_mission_success():
    """User clicks abort: mission transitions to cancelled/aborted_timeout and releases Redis lock immediately."""
    session = _FakeSession()
    mission = _create_mission(
        checkpoint={
            "version": 1,
            "takeover": {
                "challenge": "recaptcha",
            },
        }
    )
    session.add(mission)

    redis_mock = AsyncMock()
    with patch("app.services.dsh_mission_service.get_redis_client", return_value=redis_mock):
        res = await abort_takeover_mission(session, mission.id)

    assert res.status == DshMissionStatus.CANCELLED.value
    assert res.phase == "aborted_timeout"
    assert res.checkpoint["takeover"]["aborted_reason"] == "user_aborted"
    assert session.flushed is True

    takeover_key = f"dsh:lock:takeover:{mission.workspace_id}:{mission.id}"
    redis_mock.delete.assert_awaited_once_with(takeover_key)


@pytest.mark.asyncio
async def test_abort_takeover_mission_idempotent():
    """Calling abort on an already aborted mission returns it without error."""
    session = _FakeSession()
    mission = _create_mission(
        status="cancelled",
        phase="aborted_timeout",
    )
    session.add(mission)

    res = await abort_takeover_mission(session, mission.id)
    assert res.status == "cancelled"
    assert res.phase == "aborted_timeout"


@pytest.mark.asyncio
async def test_abort_takeover_mission_not_found():
    """Abort raises DshMissionServiceError when mission does not exist."""
    session = _FakeSession()
    with pytest.raises(DshMissionServiceError, match="Mission not found"):
        await abort_takeover_mission(session, uuid.uuid4())


@pytest.mark.asyncio
async def test_resume_aborted_mission_returns_409():
    """Attempting to resume an aborted mission rejects with HTTP 409 Conflict."""
    session = _FakeSession()
    user_id = uuid.uuid4()
    mission = _create_mission(
        status="cancelled",
        phase="aborted_timeout",
        user_id=user_id,
    )
    session.add(mission)

    auth_mock = MagicMock()
    auth_mock.user.id = user_id
    auth_mock.method = "session"

    with pytest.raises(HTTPException) as exc_info:
        await resume_mission(mission.id, auth_mock, session)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Mission is not in waiting_for_human phase."


@pytest.mark.asyncio
async def test_abort_mission_route():
    """POST /dsh/missions/{id}/abort route returns 200 with updated mission state."""
    session = _FakeSession()
    user_id = uuid.uuid4()
    mission = _create_mission(
        user_id=user_id,
        checkpoint={"takeover": {"challenge": "Turnstile"}},
    )
    session.add(mission)

    auth_mock = MagicMock()
    auth_mock.user.id = user_id
    auth_mock.method = "session"

    redis_mock = AsyncMock()
    with patch("app.services.dsh_mission_service.get_redis_client", return_value=redis_mock):
        response = await abort_mission(mission.id, auth_mock, session)

    assert response["mission_id"] == str(mission.id)
    assert response["status"] == "cancelled"
    assert response["phase"] == "aborted_timeout"
    assert session.committed is True


@pytest.mark.asyncio
async def test_sweep_takeovers_route():
    """POST /workspaces/{id}/dsh/missions/sweep-takeovers route executes sweep and returns swept count."""
    session = _FakeSession()
    now = datetime.now(UTC)
    expired_at = (now - timedelta(minutes=2)).isoformat()

    mission = _create_mission(
        workspace_id=42,
        checkpoint={"takeover": {"expires_at": expired_at}},
    )
    session.add(mission)

    auth_mock = MagicMock()
    membership_mock = MagicMock()
    redis_mock = AsyncMock()
    with patch("app.services.dsh_mission_service.get_redis_client", return_value=redis_mock):
        response = await sweep_takeovers(42, session, auth_mock, membership_mock)

    assert response["swept_count"] == 1
    assert "mission_ids" not in response  # No cross-tenant ID leakage
    assert session.committed is True


@pytest.mark.asyncio
async def test_abort_takeover_mission_rejects_wrong_phase():
    """Abort on a mission not in waiting_for_human raises DshMissionServiceError."""
    session = _FakeSession()
    mission = _create_mission(
        phase="crawl",  # active crawl, not waiting_for_human
    )
    session.add(mission)

    with pytest.raises(DshMissionServiceError, match="only waiting_for_human missions can be aborted"):
        await abort_takeover_mission(session, mission.id)


@pytest.mark.asyncio
async def test_abort_takeover_mission_rejects_completed():
    """Abort on a completed mission raises DshMissionServiceError."""
    session = _FakeSession()
    mission = _create_mission(
        status="success",
        phase="terminal",
    )
    session.add(mission)

    with pytest.raises(DshMissionServiceError, match="only waiting_for_human missions can be aborted"):
        await abort_takeover_mission(session, mission.id)


@pytest.mark.asyncio
async def test_abort_mission_route_409_on_wrong_phase():
    """POST /dsh/missions/{id}/abort returns 409 Conflict when mission is not waiting_for_human."""
    session = _FakeSession()
    user_id = uuid.uuid4()
    mission = _create_mission(
        user_id=user_id,
        phase="crawl",
    )
    session.add(mission)

    auth_mock = MagicMock()
    auth_mock.user.id = user_id
    auth_mock.method = "session"

    with pytest.raises(HTTPException) as exc_info:
        await abort_mission(mission.id, auth_mock, session)

    assert exc_info.value.status_code == 409
    assert "only waiting_for_human" in exc_info.value.detail
