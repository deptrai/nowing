"""Integration tests for Pro Excel deliverable download (Story 26.9b)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DshMission, User, Workspace

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


async def _create_mission(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    filename: str = "wide_research_output.xlsx",
) -> DshMission:
    mission_id = uuid4()
    mission = DshMission(
        id=mission_id,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        status="success",
        phase="terminal",
        progress_percent=100,
        payload={"query": "so sánh 20 framework", "extras": {"research_mode": "wide"}},
        checkpoint={
            "version": 1,
            "phase": "terminal",
            "subtasks": [{"id": "deliver", "status": "success"}],
            "deliverables": [
                {
                    "type": "xlsx",
                    "filename": filename,
                    "sandbox_path": "/documents/wide_research_output.xlsx",
                    "size": 7023,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(mission)
    await db_session.flush()
    return mission


@pytest.mark.asyncio
async def test_download_dsh_deliverable_returns_xlsx(
    client: AsyncClient,
    db_user: User,
    db_workspace: Workspace,
    db_session: AsyncSession,
    monkeypatch,
):
    """AC-2: Download route returns the .xlsx file with the correct MIME."""
    mission = await _create_mission(db_session, db_workspace, db_user)
    filename = "wide_research_output.xlsx"

    def _fake_get_local_sandbox_file(_thread_id: str, path: str) -> bytes | None:
        if path.endswith(filename):
            return b"fake-xlsx-content"
        return None

    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.shared.middleware.filesystem.sandbox.get_local_sandbox_file",
        _fake_get_local_sandbox_file,
    )
    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.shared.middleware.filesystem.sandbox.is_sandbox_enabled",
        lambda: True,
    )

    url = f"/api/v1/workspaces/{db_workspace.id}/dsh/missions/{mission.id}/deliverables/{filename}"
    response = await client.get(url)

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.content == b"fake-xlsx-content"


@pytest.mark.asyncio
async def test_download_dsh_deliverable_404_when_missing(
    client: AsyncClient,
    db_user: User,
    db_workspace: Workspace,
    db_session: AsyncSession,
) -> None:
    mission = await _create_mission(db_session, db_workspace, db_user)
    url = f"/api/v1/workspaces/{db_workspace.id}/dsh/missions/{mission.id}/deliverables/missing.xlsx"
    response = await client.get(url)
    assert response.status_code == 404
