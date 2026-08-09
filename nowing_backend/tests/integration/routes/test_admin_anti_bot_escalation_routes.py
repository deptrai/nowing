"""Integration tests for the admin anti-bot escalation routes.

Covers list, get, resolve, and retry endpoints with superuser and
workspace-member RBAC.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.auth.context import AuthContext
from app.db import (
    AntiBotEscalation,
    Run,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]


@pytest_asyncio.fixture
async def admin_client(
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    admin = User(
        id=uuid.uuid4(),
        email="admin@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(admin)
    await db_session.flush()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(admin)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

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


@pytest_asyncio.fixture
async def workspace_editor_client(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    user = User(
        id=uuid.uuid4(),
        email="editor@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    role = WorkspaceRole(
        workspace_id=db_workspace.id,
        name="Editor",
        permissions=["documents:read"],
        is_system_role=True,
    )
    membership = WorkspaceMembership(
        user_id=user.id,
        workspace_id=db_workspace.id,
        role=role,
    )
    db_session.add_all([user, role, membership])
    await db_session.flush()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

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


async def _seed_escalation(
    db_session: AsyncSession,
    workspace: Workspace,
    user: User,
) -> AntiBotEscalation:
    run = Run(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        capability="batdongsan.scrape",
        origin="agent",
        status="success",
        input={"city": "hanoi"},
    )
    db_session.add(run)
    await db_session.flush()

    escalation = AntiBotEscalation(
        run_id=run.id,
        workspace_id=workspace.id,
        capability="batdongsan.scrape",
        domain="batdongsan.com.vn",
        block_type="bot_detected",
        screenshot_url="https://example.com/screenshot.png",
        status="open",
        detection_count=1,
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(escalation)
    await db_session.flush()
    return escalation


@pytest.mark.asyncio
async def test_superuser_lists_escalations(
    admin_client, db_session, db_user, db_workspace
):
    await _seed_escalation(db_session, db_workspace, db_user)

    resp = await admin_client.get("/api/v1/admin/anti-bot-escalations")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] == 1
    assert body["items"][0]["domain"] == "batdongsan.com.vn"


@pytest.mark.asyncio
async def test_workspace_editor_can_filter_own_workspace(
    workspace_editor_client, db_session, db_user, db_workspace
):
    await _seed_escalation(db_session, db_workspace, db_user)

    resp = await workspace_editor_client.get(
        "/api/v1/admin/anti-bot-escalations",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_workspace_editor_cannot_list_all_workspaces(
    workspace_editor_client, db_session, db_user, db_workspace
):
    await _seed_escalation(db_session, db_workspace, db_user)

    resp = await workspace_editor_client.get("/api/v1/admin/anti-bot-escalations")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_resolve_escalation(
    admin_client, db_session, db_user, db_workspace
):
    escalation = await _seed_escalation(db_session, db_workspace, db_user)

    resp = await admin_client.post(
        f"/api/v1/admin/anti-bot-escalations/{escalation.id}/resolve"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None


@pytest.mark.asyncio
async def test_retry_escalation(
    admin_client, db_session, db_user, db_workspace
):
    escalation = await _seed_escalation(db_session, db_workspace, db_user)

    with patch("app.routes.admin_anti_bot_escalation_routes.start_async_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "retry-run-id"
        resp = await admin_client.post(
            f"/api/v1/admin/anti-bot-escalations/{escalation.id}/retry"
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "retry"
    assert body["retry_run_id"] == "retry-run-id"
