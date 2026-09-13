"""Integration test T8.4: notification + Report deliverable for each terminal state.

Verifies the full flow: run completion -> ``deep_research_complete`` Notification
created -> ``POST .../deliverable`` materializes a ``Report``. Covers success,
error, and cancelled terminal states.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.capabilities.chainlens.research.schemas import (
    ResearchOutput,
    Source,
)
from app.capabilities.core.async_runner import _notify_terminal
from app.db import (
    Notification,
    Report,
    Run,
    User,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]

limiter.enabled = False


class _DbSessionContext:
    """Make db_session usable by code that opens a fresh ``async_session_maker()``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args) -> None:
        return None


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as the workspace owner."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    # Patch async_session_maker inside async_runner so _notify_terminal sees the
    # test transaction (otherwise it opens a separate session and the row is
    # invisible inside the savepoint).
    import app.capabilities.core.async_runner as _runner

    original_asm = _runner.async_session_maker
    _runner.async_session_maker = lambda: _DbSessionContext(db_session)

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        _runner.async_session_maker = original_asm


async def _seed_run(
    db_session: AsyncSession,
    *,
    workspace_id: int,
    user_id: uuid.UUID,
    status: str = "success",
    output: ResearchOutput | None = None,
) -> Run:
    run = Run(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        capability="chainlens.research",
        origin="rest",
        status=status,
        input={"query": "Test deep research query"},
        output_text=output.model_dump_json() if output else None,
    )
    db_session.add(run)
    await db_session.flush()
    return run


@pytest.mark.asyncio
async def test_success_creates_notification_and_deliverable(
    client, db_session, db_user, db_workspace
):
    """success: Notification created, POST /deliverable creates Report."""
    output = ResearchOutput(
        status="complete",
        answer="Synthesized answer.",
        sources=[Source(url="https://example.com", title="Example")],
        resolved_mode="balanced",
        cost_micros=12_300,
    )
    run = await _seed_run(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        status="success",
        output=output,
    )

    # Trigger notification.
    await _notify_terminal(str(run.id), "success")

    notifs = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == db_user.id,
                    Notification.type == "deep_research_complete",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 1
    assert notifs[0].notification_metadata["run_id"] == f"run_{run.id}"
    assert notifs[0].notification_metadata["status"] == "success"

    # POST deliverable.
    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/runs/run_{run.id}/deliverable"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "report_id" in body

    reports = (
        (
            await db_session.execute(
                select(Report).where(Report.workspace_id == db_workspace.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(reports) == 1
    assert reports[0].report_style == "deep_research"
    assert reports[0].report_metadata["run_id"] == f"run_{run.id}"


@pytest.mark.asyncio
async def test_error_creates_notification_no_deliverable(
    client, db_session, db_user, db_workspace
):
    """error: Notification created; POST /deliverable rejected (no output)."""
    run = await _seed_run(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        status="error",
        output=None,
    )

    await _notify_terminal(str(run.id), "error")

    notifs = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == db_user.id,
                    Notification.type == "deep_research_complete",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 1
    assert notifs[0].notification_metadata["status"] == "error"

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/runs/run_{run.id}/deliverable"
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cancelled_creates_notification_no_deliverable(
    client, db_session, db_user, db_workspace
):
    """cancelled: Notification created; POST /deliverable rejected."""
    run = await _seed_run(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        status="cancelled",
        output=None,
    )

    await _notify_terminal(str(run.id), "cancelled")

    notifs = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == db_user.id,
                    Notification.type == "deep_research_complete",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 1
    assert notifs[0].notification_metadata["status"] == "cancelled"

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/runs/run_{run.id}/deliverable"
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_notification_idempotency(client, db_session, db_user, db_workspace):
    """Calling _notify_terminal multiple times creates only one Notification."""
    run = await _seed_run(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        status="success",
    )

    # Call _notify_terminal multiple times for the same run
    await _notify_terminal(str(run.id), "success")
    await _notify_terminal(str(run.id), "success")
    await _notify_terminal(str(run.id), "success")

    notifs = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == db_user.id,
                    Notification.type == "deep_research_complete",
                    Notification.notification_metadata["run_id"].as_string()
                    == f"run_{run.id}",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 1
    assert notifs[0].notification_metadata["run_id"] == f"run_{run.id}"
    assert notifs[0].notification_metadata["status"] == "success"


@pytest.mark.asyncio
async def test_deliverable_duplicate_call_returns_409(
    client, db_session, db_user, db_workspace
):
    """Calling POST /deliverable twice for the same run returns 409 on second call."""
    output = ResearchOutput(
        status="complete",
        answer="Synthesized answer.",
        sources=[Source(url="https://example.com", title="Example")],
        resolved_mode="balanced",
        cost_micros=12_300,
    )
    run = await _seed_run(
        db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        status="success",
        output=output,
    )

    # First call: should succeed (200)
    resp1 = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/runs/run_{run.id}/deliverable"
    )
    assert resp1.status_code == 200, resp1.text
    body1 = resp1.json()
    assert "report_id" in body1

    # Second call: duplicate should be blocked with 409 Conflict
    resp2 = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/runs/run_{run.id}/deliverable"
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]

    # Verify only 1 report exists in DB
    reports = (
        (
            await db_session.execute(
                select(Report).where(
                    Report.workspace_id == db_workspace.id,
                    Report.report_metadata["run_id"].as_string() == f"run_{run.id}",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(reports) == 1

