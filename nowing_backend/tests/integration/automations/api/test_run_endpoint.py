"""ATDD acceptance tests for the manual run endpoint (Story 7.7).

Verifies the ``POST /automations/{id}/run`` API against a real Postgres:

  * a manual run is created as PENDING and a real ``AutomationRun`` row
    persists, with a transient ``MANUAL`` trigger (Pattern 6 — real SQL);
  * the permission gate rejects a user without ``automations:execute``;
  * an inactive (paused) automation is rejected with HTTP 400;
  * a missing automation id maps to HTTP 404.

Assumptions (matching ``test_memory_change_trigger``): the test DB schema is
built from the ORM models; the ``enqueue_spy`` fixture patches
``automation_run_execute.apply_async`` so no Redis broker is needed.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.schemas.definition.plan_step import PlanStep
from app.db import User, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def db_viewer(db_session, db_workspace) -> User:
    """A workspace Viewer member — no automations:execute permission."""
    viewer = User(
        id=uuid.uuid4(),
        email="viewer@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(viewer)
    await db_session.flush()

    role = (
        (
            await db_session.execute(
                select(WorkspaceRole).where(
                    WorkspaceRole.workspace_id == db_workspace.id,
                    WorkspaceRole.name == "Viewer",
                )
            )
        )
        .scalars()
        .one()
    )
    db_session.add(
        WorkspaceMembership(
            user_id=viewer.id,
            workspace_id=db_workspace.id,
            role_id=role.id,
            is_owner=False,
        )
    )
    await db_session.flush()
    return viewer


@pytest_asyncio.fixture
async def viewer_client(db_session, db_viewer) -> AsyncGenerator[httpx.AsyncClient, None]:
    """An ASGI client authenticated as a Viewer (no automations:execute)."""
    from app.app import app
    from app.auth.context import AuthContext
    from app.db import get_async_session
    from app.users import get_auth_context

    async def override_session() -> AsyncGenerator:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_viewer)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def _make_automation(session, workspace, user, *, status=AutomationStatus.ACTIVE):
    definition = AutomationDefinition(
        name="manual-run automation",
        plan=[PlanStep(step_id="s1", action="agent_task")],
    )
    automation = Automation(
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        name="manual-run automation",
        status=status,
        definition=definition.model_dump(mode="json", by_alias=True),
    )
    session.add(automation)
    await session.flush()

    trigger = AutomationTrigger(
        automation_id=automation.id,
        type=TriggerType.MANUAL,
        params={},
        static_inputs={},
        enabled=True,
    )
    session.add(trigger)
    await session.flush()
    return automation


async def test_manual_run_endpoint_creates_pending_run(client, db_session, db_user, db_workspace, enqueue_spy):
    """POST /automations/{id}/run returns a PENDING run and persists a row."""
    automation = await _make_automation(db_session, db_workspace, db_user)

    resp = await client.post(f"/api/v1/automations/{automation.id}/run")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["automation_id"] == automation.id
    assert payload["status"] == "pending"

    from app.automations.persistence.models.run import AutomationRun

    row = await db_session.get(AutomationRun, payload["id"])
    assert row is not None
    assert row.automation_id == automation.id
    assert row.status.value == "pending"
    assert row.inputs.get("fired_by") == "mcp"

    assert len(enqueue_spy) == 1
    assert enqueue_spy[0]["kwargs"]["args"] == [payload["id"]]


async def test_manual_run_paused_automation_rejected(client, db_session, db_user, db_workspace, enqueue_spy):
    """A paused automation returns HTTP 400 with a readable message."""
    automation = await _make_automation(
        db_session, db_workspace, db_user, status=AutomationStatus.PAUSED
    )

    resp = await client.post(f"/api/v1/automations/{automation.id}/run")

    assert resp.status_code == 400, resp.text
    assert "not active" in resp.json()["detail"]
    assert enqueue_spy == []


async def test_manual_run_missing_automation_404(client, enqueue_spy):
    """An unknown automation id returns HTTP 404."""
    resp = await client.post("/api/v1/automations/999999/run")
    assert resp.status_code == 404, resp.text
    assert enqueue_spy == []


async def test_manual_run_requires_execute_permission(
    viewer_client, db_session, db_workspace, db_user, enqueue_spy
):
    """A Viewer (no automations:execute) gets HTTP 403, no run created."""
    automation = await _make_automation(db_session, db_workspace, db_user)

    resp = await viewer_client.post(f"/api/v1/automations/{automation.id}/run")

    assert resp.status_code == 403, resp.text
    assert enqueue_spy == []
