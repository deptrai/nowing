"""Unit tests for Projects routes (Story 3.18)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import (
    Document,
    Project,
    ProjectPinnedDocument,
    get_async_session,
)
from app.routes.projects_routes import router as projects_router
from app.users import get_auth_context

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows if rows is not None else ([value] if value is not None else [])

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


class _FakeSession:
    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.committed = False
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = 1
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def get(self, model: type, obj_id: Any) -> Any:
        if self._scalar and getattr(self._scalar, "id", None) == obj_id:
            return self._scalar
        for r in self._rows:
            if getattr(r, "id", None) == obj_id:
                return r
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        pass


def _fake_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(projects_router)
    return test_app


def test_list_projects(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="Test Project",
        description="Desc",
        master_instructions="Instructions",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    project.pinned_documents = []
    fake_session = _FakeSession(rows=[project])

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.get("/workspaces/10/projects")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Project"
        assert data[0]["master_instructions"] == "Instructions"


def test_create_project(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="New Project",
        description="Desc",
        master_instructions="Instructions",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    project.pinned_documents = []
    fake_session = _FakeSession(scalar=project)

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/10/projects",
            json={
                "name": "New Project",
                "description": "Desc",
                "master_instructions": "Instructions",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "New Project"


def test_get_project_found(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="Specific Project",
        description="Desc",
        master_instructions="Instructions",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    project.pinned_documents = []
    fake_session = _FakeSession(scalar=project)

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.get("/workspaces/10/projects/1")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == 1
        assert data["name"] == "Specific Project"


def test_get_project_not_found(app: FastAPI):
    fake_session = _FakeSession(scalar=None)

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.get("/workspaces/10/projects/999")
        assert res.status_code == 404


def test_update_project(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="Old Name",
        description="Old Desc",
        master_instructions="Old",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    project.pinned_documents = []
    fake_session = _FakeSession(scalar=project)

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.patch(
            "/workspaces/10/projects/1",
            json={"name": "Updated Name", "master_instructions": "New Instructions"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Updated Name"
        assert data["master_instructions"] == "New Instructions"


def test_delete_project(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="To Delete",
        description=None,
        master_instructions="",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    fake_session = _FakeSession(scalar=project)

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.delete("/workspaces/10/projects/1")
        assert res.status_code == 204
        assert len(fake_session.deleted) == 1


def test_archive_project(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="To Archive",
        description=None,
        master_instructions="",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    project.pinned_documents = []
    fake_session = _FakeSession(scalar=project)

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post("/workspaces/10/projects/1/archive")
        assert res.status_code == 200
        data = res.json()
        assert data["is_archived"] is True


def test_pin_document(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="Project 1",
        description=None,
        master_instructions="",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    doc = Document(
        id=101,
        workspace_id=10,
        title="Doc 1",
        source_markdown="Content",
    )
    fake_session = _FakeSession(rows=[project, doc])

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post("/workspaces/10/projects/1/documents/101/pin")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_unpin_document(app: FastAPI):
    now = datetime.now(UTC)
    project = Project(
        id=1,
        workspace_id=10,
        name="Project 1",
        description=None,
        master_instructions="",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    pin = ProjectPinnedDocument(
        id=5,
        project_id=1,
        document_id=101,
        pinned_at=now,
    )
    fake_session = _FakeSession(scalar=pin, rows=[project, pin])

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.projects_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.delete("/workspaces/10/projects/1/documents/101/pin")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
