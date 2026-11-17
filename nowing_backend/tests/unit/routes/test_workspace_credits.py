"""Unit tests for the workspace credits balance route (Story 42.4)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.dependencies.auth as auth_deps
from app.auth.context import AuthContext
from app.db import Workspace, get_async_session
from app.users import get_auth_context

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self, workspace: Any = None) -> None:
        self._workspace = workspace

    async def get(self, model: type, ident: Any) -> Any | None:
        if model is Workspace:
            return self._workspace
        return None

    async def execute(self, _stmt: Any) -> Any:
        raise AssertionError("balance route should use session.get, not execute")


def _fake_auth() -> AuthContext:
    return AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True))


def _build_client(monkeypatch: pytest.MonkeyPatch, workspace: Any) -> TestClient:
    async def _mock_access(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(auth_deps, "check_workspace_access", _mock_access)

    from app.routes.workspaces.core import router

    fake_session = _FakeSession(workspace=workspace)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_async_session] = lambda: fake_session
    app.dependency_overrides[get_auth_context] = _fake_auth
    return TestClient(app)


def test_balance_returns_credit_micros(monkeypatch: pytest.MonkeyPatch) -> None:
    """A workspace with a balance returns it in credit_micros_balance."""
    workspace = SimpleNamespace(id=1, credit_micros_balance=1500000)
    client = _build_client(monkeypatch, workspace)

    response = client.get("/workspaces/1/credits/balance")

    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == 1
    assert data["credit_micros_balance"] == 1500000


def test_balance_zero_balance_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """A workspace with a zero balance still returns 200."""
    workspace = SimpleNamespace(id=2, credit_micros_balance=0)
    client = _build_client(monkeypatch, workspace)

    response = client.get("/workspaces/2/credits/balance")

    assert response.status_code == 200
    assert response.json()["credit_micros_balance"] == 0


def test_balance_unknown_workspace_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing workspace returns 404."""
    client = _build_client(monkeypatch, None)

    response = client.get("/workspaces/999/credits/balance")

    assert response.status_code == 404
