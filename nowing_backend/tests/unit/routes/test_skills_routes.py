"""Unit tests for Skills routes (Story 3.18)."""

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
from app.db import WorkspaceSkill, get_async_session
from app.routes.skills_routes import router as skills_router
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
    test_app.include_router(skills_router)
    return test_app


def test_parse_skill_endpoint(app: FastAPI):
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: _FakeSession()

    with patch("app.routes.skills_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/10/skills/parse",
            json={
                "file_content": """---
name: Lead Radar
slug: lead-radar
trigger_pattern: "/radar"
skill_type: prompt
---
Find leads for {{city}}.
"""
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Lead Radar"
        assert data["slug"] == "lead-radar"
        assert data["trigger_pattern"] == "/radar"
        assert "Find leads for {{city}}." in data["content_markdown"]


def test_parse_skill_endpoint_invalid_yaml(app: FastAPI):
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: _FakeSession()

    with patch("app.routes.skills_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/10/skills/parse",
            json={"file_content": "No frontmatter at all"},
        )
        assert res.status_code == 400


def test_list_skills(app: FastAPI):
    now = datetime.now(UTC)
    skill = WorkspaceSkill(
        id=1,
        workspace_id=10,
        name="Lead Radar",
        slug="lead-radar",
        description="Radar desc",
        trigger_pattern="/radar",
        content_markdown="Body",
        skill_type="prompt",
        parameters_schema={},
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    fake_session = _FakeSession(rows=[skill])

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.skills_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.get("/workspaces/10/skills")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["name"] == "Lead Radar"


def test_create_skill(app: FastAPI):
    fake_session = _FakeSession(scalar=None)  # no conflict

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.routes.skills_routes.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/10/skills",
            json={
                "name": "New Skill",
                "slug": "new-skill",
                "trigger_pattern": "/new",
                "content_markdown": "Instructions",
                "skill_type": "prompt",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "New Skill"


def test_execute_skill(app: FastAPI):
    now = datetime.now(UTC)
    skill = WorkspaceSkill(
        id=1,
        workspace_id=10,
        name="Lead Radar",
        slug="lead-radar",
        description="Radar desc",
        trigger_pattern="/radar",
        content_markdown="Find leads in {{location}}.",
        skill_type="prompt",
        parameters_schema={},
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    fake_session = _FakeSession(scalar=skill)

    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    mock_exec_result = {
        "type": "prompt",
        "rendered_prompt": "Find leads in District 1.",
        "interpolated": True,
    }

    with (
        patch("app.routes.skills_routes.check_permission", AsyncMock(return_value=None)),
        patch(
            "app.routes.skills_routes.SkillExecutionService.execute",
            AsyncMock(return_value=mock_exec_result),
        ),
    ):
        client = TestClient(app)
        res = client.post(
            "/workspaces/10/skills/1/execute",
            json={"parameters": {"location": "District 1"}},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "prompt"
        assert data["rendered_prompt"] == "Find leads in District 1."
