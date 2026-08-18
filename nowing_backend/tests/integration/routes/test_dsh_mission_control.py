"""Red-phase ATDD integration tests for DSH mission control (Story 26.5).

Covers list and control endpoints, redacted checkpoints, token velocity,
and fallback to TokenUsage / Run.cost_micros.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.db import DshMission, Run, TokenUsage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


def _make_subtask(run_id: UUID | None = None, **overrides) -> dict:
    defaults = {
        "id": f"subtask-{uuid4().hex[:6]}",
        "title": "Crawl",
        "status": "success",
        "phase": "crawl",
        "reasoning_content": "Crawl reasoning",
        "tokens_used": 1000,
        "tokens_per_second": 50.0,
        "run_id": str(run_id) if run_id else str(uuid4()),
        "cost_micros": 5000,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    defaults.update(overrides)
    return defaults


async def _create_mission(
    db_session,
    db_workspace,
    db_user,
    *,
    checkpoint: dict | None = None,
    status: str = "running",
    created_at: datetime | None = None,
) -> DshMission:
    mission = DshMission(
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        mission_type="deep_lead_research",
        status=status,
        phase="reasoning",
        progress_percent=45,
        current_subtask_id="subtask-2",
        payload={"query": "secret query", "workspace_id": db_workspace.id},
        checkpoint=checkpoint
        or {
            "version": 3,
            "phase": "reasoning",
            "subtasks": [
                _make_subtask(
                    title="Crawl",
                    phase="crawl",
                    tokens_used=1200,
                    tokens_per_second=60.0,
                    cost_micros=5000,
                ),
                _make_subtask(
                    title="Reasoning",
                    phase="reasoning",
                    status="running",
                    tokens_used=3000,
                    tokens_per_second=120.0,
                    cost_micros=10000,
                ),
            ],
        },
        created_at=created_at or datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(mission)
    await db_session.flush()
    return mission


@pytest.mark.asyncio
async def test_list_missions_filters_status_and_hours(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: list endpoint returns missions filtered by status and 24h window."""
    await _create_mission(db_session, db_workspace, db_user, status="running")
    await _create_mission(
        db_session,
        db_workspace,
        db_user,
        status="success",
        created_at=datetime.now(UTC) - timedelta(hours=25),
    )

    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/dsh/missions"
        "?status=running,pending&hours=24"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert all(m["workspace_id"] == db_workspace.id for m in body["items"])
    running = [m for m in body["items"] if m["status"] == "running"]
    assert len(running) >= 1


@pytest.mark.asyncio
async def test_control_endpoint_returns_redacted_subtasks_and_token_velocity(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: control endpoint returns redacted subtasks and token_velocity."""
    mission = await _create_mission(db_session, db_workspace, db_user)

    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/dsh/missions/{mission.id}/control"
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["id"] == str(mission.id)
    assert body["workspace_id"] == db_workspace.id
    assert body["phase"] == "reasoning"
    assert body["progress_percent"] == 45
    assert "payload" not in body
    assert "sources" not in body
    assert "leads" not in body
    assert "query" not in str(body)

    assert "token_velocity" in body
    tv = body["token_velocity"]
    assert tv["tokens_total"] == 4200
    assert tv["tokens_per_second"] > 0
    assert tv["cost_micros"] == 15000
    assert tv["cost_credits"] == 0.015

    assert len(body["subtasks"]) == 2
    first = body["subtasks"][0]
    assert first["id"]
    assert first["title"]
    assert first["status"]
    assert first["phase"]
    assert "reasoning_content" in first
    assert "tokens_used" in first
    assert "cost_micros" in first


@pytest.mark.asyncio
async def test_control_endpoint_falls_back_to_token_usage(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P1: token velocity reconciles with TokenUsage when subtask tokens are empty."""
    run_id = uuid4()
    mission = await _create_mission(
        db_session,
        db_workspace,
        db_user,
        checkpoint={
            "version": 1,
            "subtasks": [
                _make_subtask(
                    run_id=run_id,
                    title="Crawl",
                    tokens_used=0,
                    tokens_per_second=0.0,
                    cost_micros=0,
                )
            ],
        },
    )

    db_session.add(
        TokenUsage(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            usage_type="dsh_mission",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=5000,
            cost_micros=8000,
            created_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/dsh/missions/{mission.id}/control"
    )
    assert resp.status_code == 200
    body = resp.json()
    tv = body["token_velocity"]
    assert tv["tokens_total"] == 5000
    assert tv["cost_micros"] == 8000


@pytest.mark.asyncio
async def test_control_endpoint_falls_back_to_run_cost_when_tokens_missing(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P1: missing token counts fall back to Run.cost_micros and show 0 tokens/sec."""
    run_id = uuid4()
    mission = await _create_mission(
        db_session,
        db_workspace,
        db_user,
        checkpoint={
            "version": 1,
            "subtasks": [
                {
                    "id": "subtask-1",
                    "title": "Crawl",
                    "status": "success",
                    "phase": "crawl",
                    "reasoning_content": "",
                    "run_id": str(run_id),
                    "started_at": datetime.now(UTC).isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            ],
        },
    )

    db_session.add(
        Run(
            id=run_id,
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            capability="chainlens.research",
            origin="api",
            status="success",
            cost_micros=12000,
            created_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/dsh/missions/{mission.id}/control"
    )
    assert resp.status_code == 200
    body = resp.json()
    tv = body["token_velocity"]
    assert tv["tokens_per_second"] == 0
    assert tv["tokens_total"] == 0
    assert tv["cost_micros"] == 12000
    assert tv["cost_credits"] == 0.012


@pytest.mark.asyncio
async def test_control_endpoint_rejects_cross_workspace(client_as_other, db_workspace):
    """P2: control endpoint returns 403 for a mission outside the caller workspace."""
    other_mission_id = uuid4()
    resp = await client_as_other.get(
        f"/api/v1/workspaces/{db_workspace.id}/dsh/missions/{other_mission_id}/control"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_control_endpoint_returns_404_for_missing_mission(
    client_as_regular_user, db_workspace
):
    """P2: control endpoint returns 404 for a non-existent mission id."""
    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/dsh/missions/{uuid4()}/control"
    )
    assert resp.status_code == 404
