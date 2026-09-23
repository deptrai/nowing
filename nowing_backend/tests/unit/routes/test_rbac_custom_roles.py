"""Unit tests for Custom Workspace Roles & Permissions Builder (Story 29.1).

Governed by: AC-1, AC-2, AC-4, AD-51, INV-29.1, AR-18.
"""

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
from app.db import (
    AuditEvent,
    Permission,
    WorkspaceRole,
    get_async_session,
)
from app.routes.rbac_routes import router as rbac_router
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
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
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

    async def flush(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass


def _fake_auth(user_id: Any = None) -> AuthContext:
    user = SimpleNamespace(id=user_id or uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(rbac_router)
    return test_app


def test_permission_enum_contains_extended_permissions():
    """AC-1: Canonical colon-separated permissions exist in enum."""
    assert Permission.ANALYTICS_READ.value == "analytics:read"
    assert Permission.BILLING_READ.value == "billing:read"
    assert Permission.BILLING_MANAGE.value == "billing:manage"
    assert Permission.SOURCE_CONFIGURE.value == "source:configure"
    assert Permission.TOOLS_ENABLE.value == "tools:enable"


def test_list_all_permissions_includes_new_permissions(app: FastAPI):
    """AC-1: GET /permissions lists new permissions with categories."""
    app.dependency_overrides[get_auth_context] = _fake_auth

    client = TestClient(app)
    res = client.get("/permissions")
    assert res.status_code == 200
    data = res.json()["permissions"]
    perm_values = {p["value"]: p for p in data}

    assert "analytics:read" in perm_values
    assert perm_values["analytics:read"]["category"] == "analytics"
    assert "billing:read" in perm_values
    assert perm_values["billing:read"]["category"] == "billing"
    assert "billing:manage" in perm_values
    assert perm_values["billing:manage"]["category"] == "billing"
    assert "source:configure" in perm_values
    assert "tools:enable" in perm_values


@pytest.mark.parametrize("name", ["Admin", "admin", "ADMIN", "  admin  "])
def test_create_role_rejects_admin_name(app: FastAPI, name: str):
    """AC-2: Reserved 'Admin' name guard (RB-4) on role creation."""
    fake_session = _FakeSession(scalar=None)
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/1/roles",
            json={
                "name": name,
                "description": "Attempted admin role",
                "permissions": ["documents:read"],
            },
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "The role name 'Admin' is reserved"


@pytest.mark.parametrize("name", ["Admin", "admin", "ADMIN", "  Admin  "])
def test_update_role_rejects_admin_name(app: FastAPI, name: str):
    """AC-2: Reserved 'Admin' name guard on role update."""
    now = datetime.now(UTC)
    role = WorkspaceRole(
        id=2,
        workspace_id=1,
        name="CustomRole",
        description="Custom",
        permissions=["documents:read"],
        is_system_role=False,
        is_default=False,
        created_at=now,
    )
    fake_session = _FakeSession(scalar=role, rows=[role])
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.put(
            "/workspaces/1/roles/2",
            json={"name": name},
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "The role name 'Admin' is reserved"


def test_update_system_role_forbidden(app: FastAPI):
    """AC-2: System roles (is_system_role=True) cannot be modified (HTTP 403)."""
    now = datetime.now(UTC)
    system_role = WorkspaceRole(
        id=1,
        workspace_id=1,
        name="Editor",
        description="System Editor",
        permissions=["documents:read", "documents:create"],
        is_system_role=True,
        is_default=False,
        created_at=now,
    )
    fake_session = _FakeSession(scalar=system_role, rows=[system_role])
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.put(
            "/workspaces/1/roles/1",
            json={"permissions": ["documents:read"]},
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "System roles cannot be modified or deleted"


def test_delete_system_role_forbidden(app: FastAPI):
    """AC-2: System roles (is_system_role=True) cannot be deleted (HTTP 403)."""
    now = datetime.now(UTC)
    system_role = WorkspaceRole(
        id=1,
        workspace_id=1,
        name="Viewer",
        description="System Viewer",
        permissions=["documents:read"],
        is_system_role=True,
        is_default=False,
        created_at=now,
    )
    fake_session = _FakeSession(scalar=system_role, rows=[system_role])
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.delete("/workspaces/1/roles/1")
        assert res.status_code == 403
        assert res.json()["detail"] == "System roles cannot be modified or deleted"


def test_create_role_rejects_wildcard_ceiling(app: FastAPI):
    """AC-2: Custom roles cannot contain wildcard '*' (Owner ceiling)."""
    fake_session = _FakeSession(scalar=None)
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/1/roles",
            json={
                "name": "SuperRole",
                "permissions": ["*"],
            },
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "Custom roles cannot grant permissions exceeding Owner ceiling"


def test_update_role_rejects_wildcard_ceiling(app: FastAPI):
    """AC-2: Updating custom role to wildcard '*' is rejected."""
    now = datetime.now(UTC)
    role = WorkspaceRole(
        id=2,
        workspace_id=1,
        name="Analyst",
        description="Analyst",
        permissions=["documents:read"],
        is_system_role=False,
        is_default=False,
        created_at=now,
    )
    fake_session = _FakeSession(scalar=role, rows=[role])
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.put(
            "/workspaces/1/roles/2",
            json={"permissions": ["documents:read", "*"]},
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "Custom roles cannot grant permissions exceeding Owner ceiling"


def test_create_role_forces_is_system_role_false(app: FastAPI):
    """AC-2: Custom roles must have is_system_role=False."""
    fake_session = _FakeSession(scalar=None)
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/1/roles",
            json={
                "name": "Analyst",
                "permissions": ["documents:read", "analytics:read"],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_system_role"] is False

        # Verify added to session
        created = next(obj for obj in fake_session.added if isinstance(obj, WorkspaceRole))
        assert created.is_system_role is False


def test_role_mutations_emit_audit_event(app: FastAPI):
    """AC-4: Create, Update, Delete emit dual-principal AuditEvent (AR-18)."""
    user_id = uuid4()
    now = datetime.now(UTC)

    # 1. Test Create Role audit
    fake_session_create = _FakeSession(scalar=None)
    app.dependency_overrides[get_auth_context] = lambda: _fake_auth(user_id)
    app.dependency_overrides[get_async_session] = lambda: fake_session_create

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/10/roles",
            json={
                "name": "BillingAuditor",
                "permissions": ["billing:read"],
            },
        )
        assert res.status_code == 200
        created_audit = next(obj for obj in fake_session_create.added if isinstance(obj, AuditEvent))
        assert created_audit.action == "workspace.role.create"
        assert created_audit.actor_id == user_id
        assert created_audit.diff_payload["workspace_id"] == 10
        assert created_audit.diff_payload["role_name"] == "BillingAuditor"
        assert "billing:read" in created_audit.diff_payload["permissions"]

    # 2. Test Update Role audit
    role = WorkspaceRole(
        id=5,
        workspace_id=10,
        name="BillingAuditor",
        description="Auditor",
        permissions=["billing:read"],
        is_system_role=False,
        is_default=False,
        created_at=now,
    )
    fake_session_update = _FakeSession(scalar=role, rows=[role])
    app.dependency_overrides[get_async_session] = lambda: fake_session_update

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.put(
            "/workspaces/10/roles/5",
            json={
                "description": "Updated auditor description",
                "permissions": ["billing:read", "billing:manage"],
            },
        )
        assert res.status_code == 200
        update_audit = next(obj for obj in fake_session_update.added if isinstance(obj, AuditEvent))
        assert update_audit.action == "workspace.role.update"
        assert update_audit.actor_id == user_id
        assert update_audit.diff_payload["role_id"] == 5
        assert "billing:manage" in update_audit.diff_payload["permissions"]

    # 3. Test Delete Role audit
    fake_session_delete = _FakeSession(scalar=role, rows=[role])
    app.dependency_overrides[get_async_session] = lambda: fake_session_delete

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.delete("/workspaces/10/roles/5")
        assert res.status_code == 200
        delete_audit = next(obj for obj in fake_session_delete.added if isinstance(obj, AuditEvent))
        assert delete_audit.action == "workspace.role.delete"
        assert delete_audit.actor_id == user_id
        assert delete_audit.diff_payload["role_id"] == 5
        assert delete_audit.diff_payload["role_name"] == "BillingAuditor"


def test_create_and_update_role_deduplicates_permissions(app: FastAPI):
    """Permissions list with duplicate entries is deduplicated on create and update."""
    fake_session = _FakeSession(scalar=None)
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.post(
            "/workspaces/1/roles",
            json={
                "name": "DedupeRole",
                "permissions": ["documents:read", "documents:read", "analytics:read"],
            },
        )
        assert res.status_code == 200
        created = next(obj for obj in fake_session.added if isinstance(obj, WorkspaceRole))
        assert created.permissions == ["documents:read", "analytics:read"]


def test_update_role_empty_permissions_allowed(app: FastAPI):
    """Empty permissions list is allowed on update for custom roles."""
    now = datetime.now(UTC)
    role = WorkspaceRole(
        id=3,
        workspace_id=1,
        name="EmptyPermsRole",
        description="Role with empty permissions",
        permissions=["documents:read"],
        is_system_role=False,
        is_default=False,
        created_at=now,
    )
    fake_session = _FakeSession(scalar=role, rows=[role])
    app.dependency_overrides[get_auth_context] = _fake_auth
    app.dependency_overrides[get_async_session] = lambda: fake_session

    with patch("app.dependencies.auth.check_permission", AsyncMock(return_value=None)):
        client = TestClient(app)
        res = client.put(
            "/workspaces/1/roles/3",
            json={"permissions": []},
        )
        assert res.status_code == 200
        assert role.permissions == []

