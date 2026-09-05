"""Integration tests for Narrative Reports routes (Story 6.12)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.auth.context import AuthContext
from app.db import (
    Permission,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def authed_workspace_setup(
    db_session: AsyncSession,
) -> tuple[AsyncClient, User, Workspace]:
    """Create a user, workspace with OWNER membership, and an authenticated client."""
    user = User(
        id=uuid4(),
        email=f"owner_{uuid4().hex[:8]}@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    workspace = Workspace(
        name=f"Workspace_{uuid4().hex[:6]}",
        user_id=user.id,
    )
    db_session.add(workspace)
    await db_session.flush()

    owner_role = WorkspaceRole(
        workspace_id=workspace.id,
        name="Owner",
        permissions=[p.value for p in Permission],
        is_system_role=True,
    )
    db_session.add(owner_role)
    await db_session.flush()

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role_id=owner_role.id,
    )
    db_session.add(membership)
    await db_session.commit()

    async def override_session():
        yield db_session

    async def override_auth():
        return AuthContext.session(user)

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0,
    ) as client:
        yield client, user, workspace

    app.dependency_overrides.pop(get_async_session, None)
    app.dependency_overrides.pop(get_auth_context, None)


async def test_get_narrative_templates(authed_workspace_setup) -> None:
    """GET /workspaces/{id}/reports/narrative/templates returns 3 canonical templates."""
    client, _user, workspace = authed_workspace_setup

    res = await client.get(f"/workspaces/{workspace.id}/reports/narrative/templates")
    assert res.status_code == 200, res.text
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    template_ids = {t["template_id"] for t in data}
    assert "news_digest" in template_ids
    assert "financial_trend" in template_ids
    assert "company_timeline" in template_ids


async def test_generate_narrative_report_success(authed_workspace_setup) -> None:
    """POST /workspaces/{id}/reports/narrative generates and persists Report."""
    client, _user, workspace = authed_workspace_setup

    payload = {
        "template_id": "news_digest",
        "title": "Custom Executive AI News Digest",
        "parameters": {
            "topic": "AI Vietnam",
            "timeframe_days": 7,
            "max_sources": 5,
        },
    }

    res = await client.post(
        f"/workspaces/{workspace.id}/reports/narrative",
        json=payload,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["id"] is not None
    assert data["title"] == "Custom Executive AI News Digest"
    assert "content" in data
    assert "report_metadata" in data
    meta = data["report_metadata"]
    assert meta["narrative_style"] == "digest"
    assert meta["template_id"] == "news_digest"


async def test_generate_narrative_report_unknown_template_404(authed_workspace_setup) -> None:
    """POST /workspaces/{id}/reports/narrative returns 404 for unknown template."""
    client, _user, workspace = authed_workspace_setup

    payload = {
        "template_id": "nonexistent_narrative_template",
        "parameters": {},
    }

    res = await client.post(
        f"/workspaces/{workspace.id}/reports/narrative",
        json=payload,
    )
    assert res.status_code == 404, res.text
    assert "not found" in res.text.lower()


async def test_generate_narrative_report_degraded_on_missing_param(authed_workspace_setup) -> None:
    """Missing required topic/symbol results in degraded report without 500 error (AC-4)."""
    client, _user, workspace = authed_workspace_setup

    payload = {
        "template_id": "financial_trend",
        "parameters": {},  # missing symbol
    }

    res = await client.post(
        f"/workspaces/{workspace.id}/reports/narrative",
        json=payload,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    meta = data["report_metadata"]
    assert meta["degraded"] is True
    assert "missing_symbol_parameter" in meta["degradation_reasons"]
    assert "Degraded Report" in data["content"]
