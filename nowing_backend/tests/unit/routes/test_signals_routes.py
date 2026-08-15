"""Red-phase ATDD tests for ``app.routes.signals_routes`` (Story 21.1).

The router is exercised end-to-end with a small FastAPI app. Auth and the
session are overridden so the tests only exercise route wiring, validation,
and response shape.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import get_async_session
from app.users import get_auth_context

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeWorkspace:
    id = 1
    name = "Test Workspace"


class _FakeSession:
    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def get(self, _model: type, _id: Any) -> Any:
        return _FakeWorkspace()

    async def commit(self) -> None:
        self.committed = True


@pytest.fixture
def fake_session():
    return _FakeSession()


def _fake_auth() -> AuthContext:
    return AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True))


async def _fake_require_workspace_member(*_args: Any, **_kwargs: Any) -> Any:
    return SimpleNamespace(id=1, user_id=uuid4(), role="owner")


async def _fake_list_signals(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }


async def _fake_detect_signals(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {
        "items": [],
        "cost_micros": 0,
        "degraded": False,
        "degradation_reasons": None,
    }


@pytest.fixture
def client(monkeypatch, fake_session):
    import app.routes.signals_routes as signals_routes

    monkeypatch.setattr(
        signals_routes,
        "require_workspace_member",
        _fake_require_workspace_member,
    )

    from app.routes.signals_routes import router

    app = FastAPI()
    app.include_router(router, prefix="/workspaces")
    app.dependency_overrides[get_async_session] = lambda: fake_session
    app.dependency_overrides[get_auth_context] = _fake_auth

    # Replace the detect endpoint with a fake so the test does not need a real
    # SignalDetectionService. list_signals is left intact so validation rules
    # are exercised.
    for r in app.routes:
        if (
            isinstance(r, APIRoute)
            and r.path == "/workspaces/{workspace_id}/signals/detect"
        ):
            r.endpoint = _fake_detect_signals
            r.dependant.call = _fake_detect_signals

    return TestClient(app)


def test_list_signals_returns_expected_shape(client):
    response = client.get("/workspaces/1/signals")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body


def test_list_signals_rejects_limit_over_100(client):
    response = client.get("/workspaces/1/signals?limit=101")
    assert response.status_code == 422
    assert "limit exceeds max 100" in response.text


def test_list_signals_rejects_inverted_date_range(client):
    response = client.get(
        "/workspaces/1/signals?from_date=2026-08-15&to_date=2026-08-01"
    )
    assert response.status_code == 400
    assert "from_date must be before to_date" in response.text


def test_detect_signals_returns_signal_output_shape(client):
    response = client.post("/workspaces/1/signals/detect", json={"company_name": "FPT"})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "cost_micros" in body
    assert "degraded" in body


def test_signals_routes_require_authentication(client, monkeypatch):
    async def _reject_auth(*_args: Any, **_kwargs: Any) -> Any:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    monkeypatch.setattr(
        "app.routes.signals_routes.require_workspace_member",
        _reject_auth,
        raising=False,
    )

    response = client.get("/workspaces/1/signals")
    assert response.status_code == 401
