"""Unit tests for workspace team memory routes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import get_async_session
from app.routes.team_memory_routes import router as team_memory_router
from app.services.memory.service import MemoryScope, SaveResult
from app.users import get_auth_context

pytestmark = pytest.mark.unit


class _FakeSession:
    async def execute(self, _stmt):
        raise AssertionError("team memory routes must not hit the DB directly")


def _fake_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(team_memory_router)
    test_app.dependency_overrides[get_auth_context] = _fake_auth
    test_app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    return test_app


@pytest.fixture
def allow_workspace_access():
    """Bypass workspace membership enforcement for all requests."""
    with patch(
        "app.dependencies.auth.check_workspace_access",
        AsyncMock(return_value=SimpleNamespace(role="owner")),
    ) as mock:
        yield mock


def test_get_team_memory(app: FastAPI, allow_workspace_access):
    with patch(
        "app.routes.team_memory_routes.read_memory",
        AsyncMock(return_value="# Team\nWe ship fast."),
    ) as mock_read:
        client = TestClient(app)
        res = client.get("/workspaces/10/memory")

        assert res.status_code == 200
        data = res.json()
        assert data["memory_md"] == "# Team\nWe ship fast."
        assert "soft" in data["limits"]
        assert "hard" in data["limits"]
        mock_read.assert_awaited_once()
        assert mock_read.call_args.kwargs["scope"] is MemoryScope.TEAM
        assert mock_read.call_args.kwargs["target_id"] == 10


def test_update_team_memory_success(app: FastAPI, allow_workspace_access):
    saved = SaveResult(status="saved", message="Saved.", memory_md="# New")

    with patch(
        "app.routes.team_memory_routes.save_memory",
        AsyncMock(return_value=saved),
    ) as mock_save:
        client = TestClient(app)
        res = client.put("/workspaces/10/memory", json={"memory_md": "# New"})

        assert res.status_code == 200
        assert res.json()["memory_md"] == "# New"
        mock_save.assert_awaited_once()
        assert mock_save.call_args.kwargs["content"] == "# New"
        assert mock_save.call_args.kwargs["scope"] is MemoryScope.TEAM


def test_update_team_memory_error_returns_400(app: FastAPI, allow_workspace_access):
    failed = SaveResult(status="error", message="Memory exceeds hard limit")

    with patch(
        "app.routes.team_memory_routes.save_memory",
        AsyncMock(return_value=failed),
    ):
        client = TestClient(app)
        res = client.put("/workspaces/10/memory", json={"memory_md": "x" * 10})

        assert res.status_code == 400
        assert res.json()["detail"] == "Memory exceeds hard limit"


def test_reset_team_memory_success(app: FastAPI, allow_workspace_access):
    reset = SaveResult(status="saved", message="Reset.", memory_md="")

    with patch(
        "app.routes.team_memory_routes.reset_memory",
        AsyncMock(return_value=reset),
    ) as mock_reset:
        client = TestClient(app)
        res = client.post("/workspaces/10/memory/reset")

        assert res.status_code == 200
        assert res.json()["memory_md"] == ""
        mock_reset.assert_awaited_once()
        assert mock_reset.call_args.kwargs["target_id"] == 10


def test_reset_team_memory_error_returns_400(app: FastAPI, allow_workspace_access):
    failed = SaveResult(status="error", message="Cannot reset")

    with patch(
        "app.routes.team_memory_routes.reset_memory",
        AsyncMock(return_value=failed),
    ):
        client = TestClient(app)
        res = client.post("/workspaces/10/memory/reset")

        assert res.status_code == 400
        assert res.json()["detail"] == "Cannot reset"
