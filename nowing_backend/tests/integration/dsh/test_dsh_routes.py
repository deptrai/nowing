from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db import DshMission

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_create_dsh_mission(client, db_workspace, db_session, monkeypatch):
    """Pattern 6: POST creates a mission row and returns a PII-safe response."""

    async def _fake_publish(_self, mission):
        return "12345-0"

    monkeypatch.setattr(
        "app.services.dsh_mission_service.DshMissionService.publish_to_stream",
        _fake_publish,
    )

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/dsh/missions",
        json={
            "mission_type": "deep_lead_research",
            "payload": {"query": "bds"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["workspace_id"] == db_workspace.id
    assert body["status"] == "pending"
    assert "id" in body
    assert "payload" not in body
    assert "checkpoint" not in body

    mission_id = uuid.UUID(body["id"])
    mission = (
        await db_session.execute(select(DshMission).where(DshMission.id == mission_id))
    ).scalar_one_or_none()
    assert mission is not None
    assert mission.mission_type == "deep_lead_research"
    assert mission.payload == {"query": "bds"}
