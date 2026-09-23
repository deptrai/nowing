"""Integration tests for workspace health & adoption analytics routes (Story 29.2, Task 5.2)."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.auth.context import AuthContext
from app.config import config as app_config
from app.db import (
    Memory,
    MemorySourceType,
    Permission,
    SearchSourceConnector,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_workspace_health_owner_full_access(
    client_as_regular_user: httpx.AsyncClient,
    db_workspace: Workspace,
) -> None:
    """Owner has full analytics access (is_public_snapshot=False, financial metrics unmasked)."""
    resp = await client_as_regular_user.get(f"/api/v1/workspaces/{db_workspace.id}/health?range=30d")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["workspace_id"] == db_workspace.id
    assert data["is_public_snapshot"] is False
    assert "total_memories" in data
    assert "query_volume" in data
    assert "active_members_dau" in data
    assert data["active_members_dau"] is not None
    assert "credits_consumed_micros" in data
    assert data["credits_consumed_micros"] is not None
    assert "quota_progress" in data
    assert data["quota_progress"] is not None
    assert "daily_metrics" in data


@pytest.mark.asyncio
async def test_get_workspace_health_public_snapshot_for_memory_read_user(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """User with only MEMORY_READ receives public snapshot with masked financials and identity."""
    # Create user with MEMORY_READ only
    user = User(
        id=uuid4(),
        email="viewer@nowing.net",
        hashed_password="hash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    role = WorkspaceRole(
        workspace_id=db_workspace.id,
        name="Memory Reader",
        description="Can only read memory",
        permissions=[Permission.MEMORY_READ.value],
        is_system_role=False,
    )
    db_session.add(role)
    await db_session.flush()

    membership = WorkspaceMembership(
        workspace_id=db_workspace.id,
        user_id=user.id,
        role_id=role.id,
        is_owner=False,
    )
    db_session.add(membership)
    await db_session.flush()

    # Create test client for this user
    async def override_session():
        yield db_session

    async def override_auth():
        return AuthContext.session(user)

    prev_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/api/v1/workspaces/{db_workspace.id}/health?range=7d")
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["is_public_snapshot"] is True
            # Masked identity and financials
            assert data.get("active_members_dau") is None
            assert data.get("active_members_wau") is None
            assert data.get("credits_consumed_micros") is None
            assert data.get("cost_per_turn_micros") is None
            assert data.get("quota_progress") is None

            # Non-masked metrics remain visible
            assert data["total_memories"] is not None
            assert data["query_volume"] is not None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prev_overrides)


@pytest.mark.asyncio
async def test_get_workspace_health_forbidden_for_non_member(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """Non-members receive 403 Forbidden."""
    unaffiliated_user = User(
        id=uuid4(),
        email="outsider@nowing.net",
        hashed_password="hash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(unaffiliated_user)
    await db_session.flush()

    async def override_session():
        yield db_session

    async def override_auth():
        return AuthContext.session(unaffiliated_user)

    prev_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/api/v1/workspaces/{db_workspace.id}/health")
            assert resp.status_code == 403
            assert "not a member" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prev_overrides)


@pytest.mark.asyncio
async def test_get_coverage_gaps_endpoint(
    client_as_regular_user: httpx.AsyncClient,
    db_workspace: Workspace,
) -> None:
    """GET /health/coverage-gaps returns gaps schema."""
    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/health/coverage-gaps"
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "gaps" in data
    assert "total_gaps" in data
    assert isinstance(data["gaps"], list)


@pytest.mark.asyncio
async def test_get_source_drilldown_not_found(
    client_as_regular_user: httpx.AsyncClient,
    db_workspace: Workspace,
) -> None:
    """GET /health/sources/{source_type} returns 404 for unknown source."""
    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/health/sources/nonexistent_connector"
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_source_drilldown_success(
    client_as_regular_user: httpx.AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """GET /health/sources/{source_type} returns source metrics and samples."""
    # Seed a memory
    memory = Memory(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        content="Testing source drilldown content sample",
        source_type=MemorySourceType.DOCUMENT,
        confidence=0.95,
        tags=["unit_test", "sample"],
        embedding=[0.1] * app_config.embedding_model_instance.dimension,
    )
    db_session.add(memory)
    await db_session.flush()

    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/health/sources/document"
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source_type"] == "document"
    assert data["total_memories"] >= 1
    assert len(data["recent_samples"]) >= 1
    assert data["recent_samples"][0]["content"] == "Testing source drilldown content sample"


@pytest.mark.asyncio
async def test_export_health_csv_and_json(
    client_as_regular_user: httpx.AsyncClient,
    db_workspace: Workspace,
) -> None:
    """GET /health/export generates CSV and JSON attachments."""
    # Test CSV export
    csv_resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/health/export?format=csv&range=7d"
    )
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers.get("content-type", "")
    assert "attachment" in csv_resp.headers.get("content-disposition", "")
    assert "total_memories" in csv_resp.text

    # Test JSON export
    json_resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/health/export?format=json&range=7d"
    )
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers.get("content-type", "")
    assert "attachment" in json_resp.headers.get("content-disposition", "")
    json_data = json_resp.json()
    assert "workspace_id" in json_data
    assert "daily_metrics" in json_data
