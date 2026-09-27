"""Unit tests for notes routes (`/workspaces/{id}/notes`)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import Document, DocumentType, get_async_session
from app.routes.notes_routes import router as notes_router
from app.users import get_auth_context

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows if rows is not None else ([value] if value is not None else [])

    def scalar(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """Session stub returning queued results for sequential execute() calls."""

    def __init__(self, results: list[_FakeResult] | None = None) -> None:
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.committed = False
        self._results = list(results or [])

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = 1
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        if not self._results:
            return _FakeResult()
        return self._results.pop(0)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)


def _fake_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


def _note(**overrides) -> Document:
    now = datetime.now(UTC)
    doc = Document(
        id=7,
        workspace_id=10,
        title="Sprint notes",
        document_type=DocumentType.NOTE,
        content="",
        content_hash="abc123",
        unique_identifier_hash="uid-7",
        document_metadata={"NOTE": True},
        source_markdown="# hi",
        status=None,
        created_at=now,
        updated_at=now,
    )
    for key, value in overrides.items():
        setattr(doc, key, value)
    return doc


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(notes_router)
    test_app.dependency_overrides[get_auth_context] = _fake_auth
    return test_app


@pytest.fixture
def allow_permission():
    with patch(
        "app.dependencies.auth.check_permission",
        AsyncMock(return_value=SimpleNamespace(role="owner")),
    ) as mock:
        yield mock


def test_create_note(app: FastAPI, allow_permission):
    fake_session = _FakeSession()
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.post(
        "/workspaces/10/notes",
        json={"title": "  Sprint notes  ", "source_markdown": "# hi"},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Sprint notes"
    assert data["document_type"] == DocumentType.NOTE.value
    assert data["workspace_id"] == 10
    assert data["document_metadata"] == {"NOTE": True}
    assert fake_session.committed
    assert len(fake_session.added) == 1


def test_create_note_blank_title_returns_400(app: FastAPI, allow_permission):
    app.dependency_overrides[get_async_session] = lambda: _FakeSession()

    client = TestClient(app)
    res = client.post("/workspaces/10/notes", json={"title": "   "})

    assert res.status_code == 400
    assert res.json()["detail"] == "Title is required"


def test_list_notes_paginated(app: FastAPI, allow_permission):
    note = _note()
    # First execute() → count query; second → page of rows.
    fake_session = _FakeSession(results=[_FakeResult(value=1), _FakeResult(rows=[note])])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.get("/workspaces/10/notes?page=0&page_size=50")

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["page_size"] == 50
    assert data["has_more"] is False
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Sprint notes"


def test_list_notes_empty(app: FastAPI, allow_permission):
    fake_session = _FakeSession(results=[_FakeResult(value=0), _FakeResult(rows=[])])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.get("/workspaces/10/notes")

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_delete_note(app: FastAPI, allow_permission):
    fake_session = _FakeSession(results=[_FakeResult(value=_note())])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.delete("/workspaces/10/notes/7")

    assert res.status_code == 200
    assert res.json()["note_id"] == 7
    assert fake_session.committed
    assert len(fake_session.deleted) == 1


def test_delete_note_not_found(app: FastAPI, allow_permission):
    fake_session = _FakeSession(results=[_FakeResult(value=None)])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.delete("/workspaces/10/notes/999")

    assert res.status_code == 404
    assert res.json()["detail"] == "Note not found"


def test_delete_note_pending_returns_409(app: FastAPI, allow_permission):
    processing = _note(status={"state": "processing"})
    fake_session = _FakeSession(results=[_FakeResult(value=processing)])
    app.dependency_overrides[get_async_session] = lambda: fake_session

    client = TestClient(app)
    res = client.delete("/workspaces/10/notes/7")

    assert res.status_code == 409
    assert "pending or being processed" in res.json()["detail"]
