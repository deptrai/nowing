"""Red-phase integration tests for Story 27.2b — Meeting Minutes REST routes."""

from __future__ import annotations

import pytest

from app.db import MeetingMinutes, Workspace


@pytest.fixture(autouse=True)
def patch_feature_flag(monkeypatch):
    """Enable the feature so tests exercise the real gate paths."""
    monkeypatch.setattr("app.config.config.MEETING_MINUTES_ENABLED", True)
    monkeypatch.setattr(
        "app.routes.meeting_minutes_routes.config.MEETING_MINUTES_ENABLED", True
    )


@pytest.mark.integration
async def test_list_meeting_minutes_requires_member(client_as_other, db_workspace):
    """AC-5: list route rejects non-members."""
    res = await client_as_other.get(
        f"/api/v1/meeting-minutes?workspace_id={db_workspace.id}"
    )
    assert res.status_code in (401, 403)


@pytest.mark.integration
async def test_all_routes_403_when_global_flag_off(
    client_as_regular_user, db_workspace, monkeypatch
):
    """AC-5/AC-6: global MEETING_MINUTES_ENABLED=false 403s all routes."""
    monkeypatch.setattr(
        "app.routes.meeting_minutes_routes.config.MEETING_MINUTES_ENABLED", False
    )
    ws = db_workspace.id
    mid = 1
    paths = [
        ("GET", f"/api/v1/meeting-minutes?workspace_id={ws}"),
        ("GET", f"/api/v1/meeting-minutes/{mid}?workspace_id={ws}"),
        ("GET", f"/api/v1/meeting-minutes/{mid}/download?workspace_id={ws}"),
        ("DELETE", f"/api/v1/meeting-minutes/{mid}?workspace_id={ws}"),
    ]
    for method, path in paths:
        if method == "DELETE":
            res = await client_as_regular_user.delete(path)
        else:
            res = await client_as_regular_user.get(path)
        assert res.status_code == 403, path


@pytest.mark.integration
async def test_create_meeting_minutes_returns_processing(
    client_as_regular_user, db_workspace
):
    """AC-1: POST creates a MeetingMinutes row and returns 202 with processing."""
    res = await client_as_regular_user.post(
        "/api/v1/meeting-minutes",
        json={
            "workspace_id": db_workspace.id,
            "audio_url": "https://example.com/meeting.mp3",
        },
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "processing"
    assert data["meeting_minutes_id"] is not None


@pytest.mark.integration
async def test_get_meeting_minutes_returns_workspace_scoped_row(
    client_as_regular_user, db_workspace, db_user, db_session
):
    """AC-4/AC-5: row is scoped to workspace and readable by member."""
    other_workspace = Workspace(name="Other Space", user_id=db_user.id)
    db_session.add(other_workspace)
    await db_session.flush()

    foreign = MeetingMinutes(
        workspace_id=other_workspace.id,
        user_id=db_user.id,
        status="ready",
        title="Foreign",
    )
    db_session.add(foreign)
    await db_session.flush()

    res = await client_as_regular_user.get(
        f"/api/v1/meeting-minutes/{foreign.id}?workspace_id={db_workspace.id}"
    )
    assert res.status_code == 404


@pytest.mark.integration
async def test_delete_meeting_minutes_removes_row(
    client_as_regular_user, db_workspace, db_session
):
    """AC-4/AC-6: DELETE removes row and subsequent GET returns 404."""
    res = await client_as_regular_user.post(
        "/api/v1/meeting-minutes",
        json={
            "workspace_id": db_workspace.id,
            "audio_url": "https://example.com/meeting.mp3",
        },
    )
    mid = res.json()["meeting_minutes_id"]
    del_res = await client_as_regular_user.delete(
        f"/api/v1/meeting-minutes/{mid}?workspace_id={db_workspace.id}"
    )
    assert del_res.status_code == 204
    get_res = await client_as_regular_user.get(
        f"/api/v1/meeting-minutes/{mid}?workspace_id={db_workspace.id}"
    )
    assert get_res.status_code == 404
