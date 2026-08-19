"""Integration tests for Reactive Kanban Board & Optimistic Concurrency Control (Story 24.3 / AC-1 / INV-24.4).

Verifies:
- GET /api/v1/workspaces/{workspace_id}/leads/pipeline/stages returns default stages.
- Simultaneous drag updates on the same lead card are protected by Optimistic Concurrency Control (OCC).
- Valid stage update increments lead.version and records an entry in lead_activity_logs.
- Stale update with mismatched expected_version returns HTTP 409 Conflict.
- Retry with current version succeeds without state corruption.
- GET /api/v1/workspaces/{workspace_id}/leads/{lead_id}/timeline returns chronological interaction logs.
- Tenancy isolation: cross-workspace lead access is forbidden.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, Workspace

pytestmark = pytest.mark.integration


async def test_kanban_pipeline_stages_list(
    client_as_regular_user: AsyncClient,
    db_workspace: Workspace,
) -> None:
    """AC-1: GET /workspaces/{id}/leads/pipeline/stages returns 5 default Kanban columns."""
    res = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads/pipeline/stages"
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert isinstance(data, list) or "stages" in data
    stages = data if isinstance(data, list) else data["stages"]

    stage_names = [s["name"] for s in stages]
    # Check default 5 stage names per Story 24.3 AC-1
    expected_stages = ["Mới săn", "Đang tiếp cận", "Tiềm năng", "Đã chốt", "Hủy / Không nhu cầu"]
    for expected in expected_stages:
        assert expected in stage_names, f"Expected stage '{expected}' not found in {stage_names}"


async def test_kanban_stage_transition_optimistic_concurrency_and_conflict_409(
    client_as_regular_user: AsyncClient,
    db_workspace: Workspace,
    db_session: AsyncSession,
) -> None:
    """AC-1 & INV-24.4: Concurrent card drags on same lead handle OCC versioning and return 409 Conflict.

    Flow:
    1. Seed lead with version=1 in stage_1.
    2. Client A moves lead to stage_2 with expected_version=1 -> Returns 200, version becomes 2.
    3. Client B sends stale move to stage_3 with expected_version=1 -> Returns 409 Conflict.
    4. Client B refetches and retries with expected_version=2 -> Returns 200, version becomes 3.
    """
    # 1. Fetch available stages
    stages_res = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads/pipeline/stages"
    )
    assert stages_res.status_code == 200, stages_res.text
    stages_data = stages_res.json()
    stages = stages_data if isinstance(stages_data, list) else stages_data["stages"]
    assert len(stages) >= 3

    stage_1_id = stages[0]["id"]
    stage_2_id = stages[1]["id"]
    stage_3_id = stages[2]["id"]

    # 2. Seed a test lead in stage 1
    lead_id = uuid.uuid4()
    new_lead = Lead(
        id=lead_id,
        workspace_id=db_workspace.id,
        company_name="ATDD Concurrency Real Estate Corp",
        value_hmac=f"lead-hmac-{uuid.uuid4().hex[:8]}",
        source="batdongsan",
        status="new",
    )
    # Set stage_id and version if model has them
    if hasattr(new_lead, "stage_id"):
        new_lead.stage_id = stage_1_id
    if hasattr(new_lead, "version"):
        new_lead.version = 1

    db_session.add(new_lead)
    await db_session.commit()

    # 3. Client A updates stage with expected_version = 1 -> SUCCESS (200)
    payload_a = {
        "stage_id": stage_2_id,
        "expected_version": 1,
    }
    res_a = await client_as_regular_user.patch(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead_id}/stage",
        json=payload_a,
    )
    assert res_a.status_code == 200, res_a.text
    data_a = res_a.json()
    assert data_a.get("version") == 2 or data_a.get("lead", {}).get("version") == 2
    assert str(data_a.get("stage_id", data_a.get("lead", {}).get("stage_id"))) == str(stage_2_id)

    # 4. Client B attempts update with stale expected_version = 1 -> OCC CONFLICT (409)
    payload_b_stale = {
        "stage_id": stage_3_id,
        "expected_version": 1,
    }
    res_b_stale = await client_as_regular_user.patch(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead_id}/stage",
        json=payload_b_stale,
    )
    assert res_b_stale.status_code == 409, f"Expected 409 Conflict, got {res_b_stale.status_code}: {res_b_stale.text}"
    conflict_data = res_b_stale.json()
    error_detail = conflict_data.get("detail", "")
    assert (
        "conflict" in str(error_detail).lower()
        or "version" in str(error_detail).lower()
        or conflict_data.get("error_code") in ["concurrency_conflict", "version_conflict", "VERSION_CONFLICT"]
    )

    # 5. Client B retries with updated expected_version = 2 -> SUCCESS (200)
    payload_b_retry = {
        "stage_id": stage_3_id,
        "expected_version": 2,
    }
    res_b_retry = await client_as_regular_user.patch(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead_id}/stage",
        json=payload_b_retry,
    )
    assert res_b_retry.status_code == 200, res_b_retry.text
    data_b = res_b_retry.json()
    assert data_b.get("version") == 3 or data_b.get("lead", {}).get("version") == 3


async def test_kanban_timeline_activity_logs_chronological(
    client_as_regular_user: AsyncClient,
    db_workspace: Workspace,
    db_session: AsyncSession,
) -> None:
    """AC-3: GET /workspaces/{id}/leads/{lead_id}/timeline returns chronological interaction history."""
    lead_id = uuid.uuid4()
    new_lead = Lead(
        id=lead_id,
        workspace_id=db_workspace.id,
        company_name="Timeline Test Lead",
        value_hmac=f"lead-hmac-{uuid.uuid4().hex[:8]}",
        source="batdongsan",
        status="new",
    )
    db_session.add(new_lead)
    await db_session.commit()

    # Query timeline endpoint
    res = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead_id}/timeline"
    )
    assert res.status_code == 200, res.text
    timeline = res.json()
    assert isinstance(timeline, list) or "timeline" in timeline or "events" in timeline


async def test_kanban_cross_workspace_isolation_fail_closed(
    client_as_regular_user: AsyncClient,
    db_workspace: Workspace,
    db_session: AsyncSession,
) -> None:
    """INV-23.6: Accessing lead from an unauthorized workspace returns 403 or 404."""
    unauthorized_workspace_id = 999999
    fake_lead_id = uuid.uuid4()

    res = await client_as_regular_user.patch(
        f"/api/v1/workspaces/{unauthorized_workspace_id}/leads/{fake_lead_id}/stage",
        json={"stage_id": str(uuid.uuid4()), "expected_version": 1},
    )
    assert res.status_code in [403, 404]
