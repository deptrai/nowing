"""Unit tests for Workspace Tables and Multi-Table Tabs routes (Story 21.13)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import Workspace, WorkspaceTable, get_async_session
from app.users import get_auth_context

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value if self._value is not None else 0

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(
        self,
        *,
        tables: list[Any] | None = None,
        workspace: Any = None,
    ) -> None:
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.committed = False
        self._tables = tables or []
        self._workspace = workspace or SimpleNamespace(id=1, name="Test Workspace")

    def add(self, obj: Any) -> None:
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        if not hasattr(obj, "updated_at") or obj.updated_at is None:
            obj.updated_at = None
        self.added.append(obj)
        self._tables.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)
        if obj in self._tables:
            self._tables.remove(obj)

    async def execute(self, stmt: Any) -> _FakeResult:
        stmt_str = str(stmt)
        if "workspace_tables" in stmt_str.lower() or "workspace_id" in stmt_str:
            return _FakeResult(rows=self._tables)
        return _FakeResult(rows=self._tables)

    async def get(self, model: type, ident: Any) -> Any:
        if model is Workspace:
            return self._workspace
        if model is WorkspaceTable:
            for t in self._tables:
                if str(t.id) == str(ident):
                    return t
            return None
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        pass


def _create_mock_table(
    *,
    table_id: UUID | None = None,
    workspace_id: int = 1,
    name: str = "Bất Động Sản Hà Nội",
    icon: str = "home",
    filter_preset: dict[str, Any] | None = None,
    columns_config: dict[str, Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=table_id or uuid4(),
        workspace_id=workspace_id,
        name=name,
        icon=icon,
        filter_preset=filter_preset or {"source": "batdongsan"},
        columns_config=columns_config
        or {"visible_columns": ["company_name", "phone", "fit_score"]},
        created_at=datetime.now(UTC),
        updated_at=None,
    )


def _fake_auth() -> AuthContext:
    return AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True))


@pytest.fixture
def mock_tables():
    return [
        _create_mock_table(name="BĐS Hà Nội", icon="home"),
        _create_mock_table(name="Tech Recruitment", icon="briefcase"),
    ]


@pytest.fixture
def client(monkeypatch, mock_tables):
    import app.routes.workspace_tables_routes as wt_routes

    async def _mock_check_perm(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(wt_routes, "check_permission", _mock_check_perm)

    from app.routes.workspace_tables_routes import router

    fake_session = _FakeSession(tables=mock_tables)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_async_session] = lambda: fake_session
    app.dependency_overrides[get_auth_context] = _fake_auth

    return TestClient(app)


def test_list_workspace_tables(client, mock_tables):
    response = client.get("/workspaces/1/tables")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "BĐS Hà Nội"
    assert data[0]["icon"] == "home"


def test_create_workspace_table(client):
    payload = {
        "name": "Social Leads (Facebook)",
        "icon": "users",
        "filter_preset": {"source": "facebook", "min_score": 80},
        "columns_config": {"visible_columns": ["company_name", "fit_score"]},
    }
    response = client.post("/workspaces/1/tables", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Social Leads (Facebook)"
    assert data["icon"] == "users"
    assert data["filter_preset"]["source"] == "facebook"
    assert "id" in data


def test_update_workspace_table(client, mock_tables):
    table_id = mock_tables[0].id
    payload = {
        "name": "BĐS Toàn Quốc",
        "icon": "building",
    }
    response = client.patch(f"/workspaces/1/tables/{table_id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "BĐS Toàn Quốc"
    assert data["icon"] == "building"


def test_delete_workspace_table(client, mock_tables):
    table_id = mock_tables[0].id
    response = client.delete(f"/workspaces/1/tables/{table_id}")
    assert response.status_code == 204
