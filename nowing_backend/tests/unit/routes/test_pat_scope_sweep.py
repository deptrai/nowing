"""Unit tests for Spec 42.9 PAT scope sweep over lead/credits routes.

Tái sử dụng pattern fake-auth/monkeypatch từ ``test_lead_batch_ingest.py``
và ``test_workspace_credits.py``. Ma trận: READ_OK, READ_NO_SCOPE,
WRITE_OK, WRITE_NO_SCOPE, PAT_WRONG_WS, BALANCE_PAT, GATE_MESSAGE,
SESSION_UNCHANGED.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.lead_batch_routes as lead_batch_routes
from app.auth.context import AuthContext
from app.db import Workspace, get_async_session
from app.users import get_auth_context

pytestmark = pytest.mark.unit


def _pat_auth(
    *, scopes: list[str], workspace_id: int | None, pat_id: int = 77
) -> AuthContext:
    pat = SimpleNamespace(
        id=pat_id,
        token_prefix="nwp_test",
        workspace_id=workspace_id,
        scopes=scopes,
    )
    return AuthContext.pat_auth(SimpleNamespace(id=uuid4(), is_active=True), pat)


class _FakeResult:
    """Kết quả execute() giả — hỗ trợ scalar_one/scalar_one_or_none/scalars."""

    def __init__(self, first: Any = None, scalar: Any = None, all_: Any = None) -> None:
        self._first = first
        self._scalar = scalar
        self._all = all_ if all_ is not None else []

    def scalar_one(self) -> Any:
        return self._scalar

    def scalar_one_or_none(self) -> Any:
        return self._first

    def scalars(self) -> "_FakeResult":
        return self

    def first(self) -> Any:
        return self._first

    def all(self) -> list[Any]:
        return self._all


class _FakeSession:
    """Session giả cho route leads/credits — Workspace trả về qua execute()."""

    def __init__(self, workspace: Any = None) -> None:
        self._workspace = workspace
        self.added: list[Any] = []
        # execute() mặc định trả Workspace; route unlock có thể override.
        self.execute_result: Any = None

    async def get(self, model: type, ident: Any) -> Any | None:
        if model is Workspace:
            return self._workspace
        return None

    async def execute(self, _stmt: Any, _params: Any | None = None) -> Any:
        if self.execute_result is not None:
            return self.execute_result
        # scalar=0 cho count query; first=workspace cho select Workspace.
        return _FakeResult(first=self._workspace, scalar=0)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def flush(self) -> None:
        pass


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    auth: AuthContext,
    workspace: Any = None,
    include_router: bool = True,
) -> TestClient:
    """Client chung: mock check_permission + session giả + auth override."""
    monkeypatch.setattr(
        "app.dependencies.auth.check_permission", AsyncMock(return_value=None)
    )

    fake_session = _FakeSession(workspace=workspace)

    async def _fake_session():
        yield fake_session

    app = FastAPI()
    if include_router:
        app.include_router(lead_batch_routes.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[get_auth_context] = lambda: auth
    client = TestClient(app)
    client.fake_session = fake_session  # type: ignore[attr-defined]
    return client


def _post_unlock(client: TestClient, lead_id: Any) -> Any:
    return client.post(
        f"/api/v1/workspaces/1/leads/{lead_id}/contacts/{uuid4()}/unlock",
        headers={"X-Forwarded-For": str(uuid4())},
    )


def _stub_contact_unlock(monkeypatch: pytest.MonkeyPatch, session: Any) -> None:
    """Mock ContactUnlockService.unlock_contact + contact lookup cho route."""

    async def _mock_unlock(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            contact_id=uuid4(),
            is_unlocked=True,
            cost_micros=1500,
            name=None,
            title=None,
            email=None,
            phone=None,
        )

    monkeypatch.setattr(
        lead_batch_routes.ContactUnlockService,
        "unlock_contact",
        AsyncMock(side_effect=_mock_unlock),
    )
    # Contact lookup (execute → scalar_one_or_none) trả contact giả.
    session.execute_result = _FakeResult(
        first=SimpleNamespace(id=uuid4(), workspace_id=1)
    )


# ---------------------------------------------------------------------------
# WRITE_OK / WRITE_NO_SCOPE / PAT_WRONG_WS — unlock-contact (lead_batch)
# ---------------------------------------------------------------------------


def test_write_ok_pat_with_leads_write_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT leads:write đúng workspace → unlock-contact 200."""
    client = _build_client(
        monkeypatch, _pat_auth(scopes=["leads:write"], workspace_id=1), workspace=SimpleNamespace(id=1)
    )
    _stub_contact_unlock(monkeypatch, client.fake_session)
    response = _post_unlock(client, uuid4())
    assert response.status_code == 200


def test_write_no_scope_pat_missing_leads_write_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT chỉ có leads:read → 403 'permission missing: leads:write'."""
    client = _build_client(
        monkeypatch, _pat_auth(scopes=["leads:read"], workspace_id=1), workspace=SimpleNamespace(id=1)
    )
    response = _post_unlock(client, uuid4())
    assert response.status_code == 403
    assert "permission missing: leads:write" in response.json()["detail"]


def test_pat_wrong_ws_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """PAT bound ws 999 gọi route ws 1 → 403 'workspace_id outside pat scope'."""
    client = _build_client(
        monkeypatch, _pat_auth(scopes=["leads:write"], workspace_id=999), workspace=SimpleNamespace(id=1)
    )
    response = _post_unlock(client, uuid4())
    assert response.status_code == 403
    assert response.json()["detail"] == "workspace_id outside pat scope"


# ---------------------------------------------------------------------------
# SESSION_UNCHANGED — session caller vẫn pass-through, không bị PAT gate
# ---------------------------------------------------------------------------


def test_session_unchanged_unlock_contact_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session auth pass-through RequirePatScope → 200 như cũ."""
    client = _build_client(
        monkeypatch,
        AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True)),
        workspace=SimpleNamespace(id=1),
    )
    _stub_contact_unlock(monkeypatch, client.fake_session)
    response = _post_unlock(client, uuid4())
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# READ_OK / READ_NO_SCOPE — list leads (leads_routes)
# ---------------------------------------------------------------------------


def _build_leads_client(
    monkeypatch: pytest.MonkeyPatch,
    auth: AuthContext,
    workspace: Any = None,
) -> TestClient:
    """Client cho leads router; mock check_permission trả membership owner."""
    import app.dependencies.auth as auth_deps

    workspace = workspace or SimpleNamespace(
        id=1, api_access_enabled=True, credit_micros_balance=0
    )
    membership = SimpleNamespace(is_owner=True, role=None, user_id=uuid4())

    async def _mock_perm(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return membership

    monkeypatch.setattr(auth_deps, "check_permission", _mock_perm)

    fake_session = _FakeSession(workspace=workspace)

    async def _fake_session():
        yield fake_session

    import app.routes.leads_routes as leads_routes

    app = FastAPI()
    app.include_router(leads_routes.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[get_auth_context] = lambda: auth
    leads_client = TestClient(app)
    leads_client.fake_session = fake_session  # type: ignore[attr-defined]
    return leads_client


def test_read_ok_pat_with_leads_read_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT leads:read → GET /leads 200."""
    client = _build_leads_client(
        monkeypatch, _pat_auth(scopes=["leads:read"], workspace_id=1)
    )
    response = client.get("/api/v1/workspaces/1/leads")
    assert response.status_code == 200


def test_read_no_scope_pat_missing_leads_read_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT chỉ có leads:write → GET /leads 403 'permission missing: leads:read'."""
    client = _build_leads_client(
        monkeypatch, _pat_auth(scopes=["leads:write"], workspace_id=1)
    )
    response = client.get("/api/v1/workspaces/1/leads")
    assert response.status_code == 403
    assert "permission missing: leads:read" in response.json()["detail"]


# ---------------------------------------------------------------------------
# BALANCE_PAT — GET /credits/balance với PAT leads:read (D1)
# ---------------------------------------------------------------------------


def test_balance_pat_with_leads_read_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT leads:read → GET /credits/balance 200 với balance."""
    import app.dependencies.auth as auth_deps

    async def _mock_access(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(auth_deps, "check_workspace_access", _mock_access)

    from app.routes.workspaces.core import router as workspaces_router

    auth = _pat_auth(scopes=["leads:read"], workspace_id=1)
    fake_session = _FakeSession(
        workspace=SimpleNamespace(id=1, credit_micros_balance=1500000)
    )

    async def _fake_session():
        yield fake_session

    app = FastAPI()
    app.include_router(workspaces_router)
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[get_auth_context] = lambda: auth
    client = TestClient(app)

    response = client.get("/workspaces/1/credits/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == 1
    assert data["credit_micros_balance"] == 1500000


# ---------------------------------------------------------------------------
# GATE_MESSAGE — PAT trên workspace api_access_enabled=False → 403 hint
# ---------------------------------------------------------------------------


def test_gate_message_403_contains_api_access_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT trên workspace chưa bật api-access → 403 detail chứa 'api-access'."""
    from app.utils import rbac

    import app.routes.leads_routes as leads_routes

    # Workspace tắt api_access_enabled; membership owner để qua check_permission
    # thật rồi chạm _enforce_api_access_gate.
    workspace = SimpleNamespace(id=1, api_access_enabled=False)
    membership = SimpleNamespace(is_owner=True, role=None, user_id=uuid4())
    monkeypatch.setattr(
        rbac, "get_user_membership", AsyncMock(return_value=membership)
    )

    auth = _pat_auth(scopes=["leads:read"], workspace_id=1)
    fake_session = _FakeSession(workspace=workspace)

    async def _fake_session():
        yield fake_session

    app = FastAPI()
    app.include_router(leads_routes.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[get_auth_context] = lambda: auth
    client = TestClient(app)

    response = client.get(
        "/api/v1/workspaces/1/leads",
        headers={"X-Forwarded-For": str(uuid4())},
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "api-access" in detail
    assert "API_ACCESS_MANAGE" in detail
