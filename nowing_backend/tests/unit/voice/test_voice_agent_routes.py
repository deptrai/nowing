"""Unit tests for Voice Agent BYO-SIP REST API (Story 38.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import get_async_session
from app.routes.voice_agent import router as voice_agent_router
from app.users import require_session_context

pytestmark = pytest.mark.unit


def _auth(is_superuser: bool = False) -> AuthContext:
    user = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=is_superuser,
    )
    return AuthContext.session(user)


def _mock_session_with_role(role_name: str | None) -> AsyncMock:
    """Async session whose execute() resolves the RBAC role query."""
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = role_name
    session.execute = AsyncMock(return_value=res)
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(voice_agent_router)
    return test_app


@pytest.fixture
def client(app: FastAPI):
    return TestClient(app)


class TestSipTrunkEndpoints:
    """CRUD + RBAC for /api/v1/workspaces/{ws}/voice/trunks."""

    def test_superuser_creates_trunk_returns_201_masked_password(self, app, client):
        now = datetime.now(UTC)
        mock_trunk = SimpleNamespace(
            id=uuid4(),
            workspace_id=15,
            name="Viettel",
            brandname="NOWING",
            outbound_did="+842871099999",
            sip_server="sip.viettel.vn:5060",
            sip_username="u1",
            livekit_trunk_id="lk_1",
            is_default=True,
            is_verified=False,
            status="active",
            created_at=now,
            updated_at=now,
        )

        mock_session = AsyncMock()

        async def _gen():
            yield mock_session

        app.dependency_overrides[get_async_session] = _gen
        app.dependency_overrides[require_session_context] = lambda: _auth(
            is_superuser=True
        )

        from app.routes.voice_agent import _get_sip_manager

        mock_mgr = MagicMock()
        mock_mgr.create_trunk = AsyncMock(return_value=mock_trunk)
        app.dependency_overrides[_get_sip_manager] = lambda: mock_mgr

        resp = client.post(
            "/api/v1/workspaces/15/voice/trunks",
            json={
                "name": "Viettel Trunk",
                "outbound_did": "+842871099999",
                "sip_server": "sip.viettel.vn:5060",
                "sip_username": "u1",
                "sip_password": "super_secret_password",
            },
        )

        app.dependency_overrides.pop(_get_sip_manager, None)

        assert resp.status_code == 201
        body = resp.json()
        assert body["sip_password_masked"] == "********"
        assert body.get("sip_password") is None

    def test_member_role_forbidden(self, app, client):
        """Non-admin workspace members cannot manage SIP trunks."""
        mock_session = _mock_session_with_role("member")

        async def _gen():
            yield mock_session

        app.dependency_overrides[get_async_session] = _gen
        app.dependency_overrides[require_session_context] = lambda: _auth(
            is_superuser=False
        )

        resp = client.post(
            "/api/v1/workspaces/15/voice/trunks",
            json={
                "name": "X",
                "outbound_did": "+842871099999",
                "sip_server": "sip.x.vn:5060",
                "sip_username": "u",
                "sip_password": "p",
            },
        )

        assert resp.status_code == 403

    def test_cross_workspace_access_forbidden(self, app, client):
        """Owner of ws=15 has no membership in ws=99 → 403."""
        mock_session = _mock_session_with_role(None)  # No membership in ws=99

        async def _gen():
            yield mock_session

        app.dependency_overrides[get_async_session] = _gen
        app.dependency_overrides[require_session_context] = lambda: _auth(
            is_superuser=False
        )

        resp = client.get("/api/v1/workspaces/99/voice/trunks")

        assert resp.status_code == 403

    def test_owner_role_can_list_trunks(self, app, client):
        """Workspace owner (DB role 'owner') can list trunks."""
        mock_session = _mock_session_with_role("owner")

        async def _gen():
            yield mock_session

        app.dependency_overrides[get_async_session] = _gen
        app.dependency_overrides[require_session_context] = lambda: _auth(
            is_superuser=False
        )

        from app.routes.voice_agent import _get_sip_manager

        mock_mgr = MagicMock()
        mock_mgr.list_trunks = AsyncMock(return_value=[])
        app.dependency_overrides[_get_sip_manager] = lambda: mock_mgr

        resp = client.get("/api/v1/workspaces/15/voice/trunks")

        app.dependency_overrides.pop(_get_sip_manager, None)

        assert resp.status_code == 200
        assert resp.json() == []
