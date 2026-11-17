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

    async def refresh(self, _obj: Any) -> None:
        # Mô phỏng DB gán PK sau commit (route đọc lại id để build response).
        if getattr(_obj, "id", None) is None:
            _obj.id = 1


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


# ---------------------------------------------------------------------------
# Scope pinning — review 42.9: trước chỉ 3/11 site được pin test, sai-wiring
# sẽ ship green. Ma trận dưới pin đúng scope khai báo của từng endpoint.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,json_body,required_scope",
    [
        ("get", "/api/v1/workspaces/1/leads/lead-uuid", None, "leads:read"),
        (
            "patch",
            "/api/v1/workspaces/1/leads/lead-uuid/status",
            {"status": "open"},
            "leads:write",
        ),
        ("get", "/api/v1/workspaces/1/companies/acme/graph", None, "leads:read"),
        (
            "post",
            "/api/v1/workspaces/1/leads/reverse-icp",
            {"url": "https://example.com"},
            "leads:read",
        ),
        (
            "post",
            "/api/v1/workspaces/1/leads/lead-uuid/resolve-phone",
            {},
            "leads:enrich",
        ),
        (
            "post",
            "/api/v1/workspaces/1/leads/lead-uuid/report-invalid-phone",
            {},
            "leads:write",
        ),
    ],
    ids=[
        "get_lead",
        "update_lead_status",
        "get_company_graph",
        "reverse_icp",
        "resolve_phone_needs_enrich",
        "report_invalid_phone",
    ],
)
def test_leads_routes_wrong_scope_403(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    json_body: dict | None,
    required_scope: str,
) -> None:
    """PAT sai scope → 403 'permission missing: <scope>' đúng từng endpoint."""
    wrong_scopes = (
        ["leads:read"] if required_scope == "leads:write" else ["leads:write"]
    )
    client = _build_leads_client(
        monkeypatch, _pat_auth(scopes=wrong_scopes, workspace_id=1)
    )

    url = path.replace("lead-uuid", str(uuid4()))
    response = client.request(
        method, url, json=json_body if json_body is not None else None
    )

    assert response.status_code == 403
    assert f"permission missing: {required_scope}" in response.json()["detail"]


@pytest.mark.parametrize(
    "path,json_body",
    [
        ("/api/v1/workspaces/1/leads/lead-uuid/contacts/contact-uuid/relock", None),
        (
            "/api/v1/workspaces/1/pii-opt-out",
            {"record_type": "phone", "value": "0901"},
        ),
    ],
    ids=["relock_contact", "pii_opt_out"],
)
def test_batch_write_wrong_scope_403(
    monkeypatch: pytest.MonkeyPatch, path: str, json_body: dict | None
) -> None:
    """PAT chỉ có leads:read → 403 trên relock + pii_opt_out."""
    client = _build_client(
        monkeypatch, _pat_auth(scopes=["leads:read"], workspace_id=1)
    )
    url = path.replace("lead-uuid", str(uuid4())).replace(
        "contact-uuid", str(uuid4())
    )
    response = client.post(
        url, json=json_body if json_body is not None else None
    )
    assert response.status_code == 403
    assert "permission missing: leads:write" in response.json()["detail"]


def test_resolve_phone_pat_respects_api_access_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT leads:enrich trên ws api_access_enabled=False → 403 api-access.

    Review 42.9: resolve-phone vốn bypass gate (chỉ check perms inline qua
    get_user_permissions, không qua check_permission). Patch thêm
    `_enforce_api_access_gate` sau perms — test này pin hành vi mới.
    """
    import app.routes.leads_routes as leads_routes

    workspace = SimpleNamespace(id=1, api_access_enabled=False)
    client = _build_leads_client(
        monkeypatch,
        _pat_auth(scopes=["leads:enrich"], workspace_id=1),
        workspace=workspace,
    )
    # PAT user đã có perm enrich → qua inline check, đến gate mới thì 403.
    monkeypatch.setattr(
        leads_routes,
        "get_user_permissions",
        AsyncMock(return_value={"leads:enrich"}),
    )

    response = client.post(
        f"/api/v1/workspaces/1/leads/{uuid4()}/resolve-phone", json={}
    )
    assert response.status_code == 403
    assert "api-access" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Spec 42-10 — PAT scope sweep trên enrichment / scoring / outbound routes
# ---------------------------------------------------------------------------


def _build_router_client(
    monkeypatch: pytest.MonkeyPatch,
    router: Any,
    auth: AuthContext,
    workspace: Any = None,
) -> TestClient:
    """Client cho router bất kỳ: mock check_permission + session giả + auth."""
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

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[get_auth_context] = lambda: auth
    try:
        from app.redis_client import get_redis_client

        app.dependency_overrides[get_redis_client] = lambda: None
    except Exception:
        pass
    client = TestClient(app)
    client.fake_session = fake_session  # type: ignore[attr-defined]
    return client


@pytest.mark.parametrize(
    "router_name,method,path,json_body,required_scope",
    [
        # enrichment_routes — leads:enrich ×3, leads:read ×2
        (
            "enrichment_routes",
            "post",
            "/api/v1/workspaces/1/leads/enrich",
            {"lead_ids": [str(uuid4())]},
            "leads:enrich",
        ),
        (
            "enrichment_routes",
            "get",
            "/api/v1/workspaces/1/leads/enrich/cost",
            None,
            "leads:enrich",
        ),
        (
            "enrichment_routes",
            "post",
            "/api/v1/workspaces/1/leads/{lead_id}/enrich",
            {},
            "leads:enrich",
        ),
        (
            "enrichment_routes",
            "get",
            "/api/v1/workspaces/1/leads/{lead_id}/contacts",
            None,
            "leads:read",
        ),
        (
            "enrichment_routes",
            "get",
            "/api/v1/workspaces/1/leads/{lead_id}/enrichments",
            None,
            "leads:read",
        ),
        # lead_scoring_routes — leads:score, leads:read ×3, leads:write (D1)
        (
            "lead_scoring_routes",
            "post",
            "/api/v1/workspaces/1/leads/score",
            {},
            "leads:score",
        ),
        (
            "lead_scoring_routes",
            "get",
            "/api/v1/workspaces/1/leads/scores",
            None,
            "leads:read",
        ),
        (
            "lead_scoring_routes",
            "get",
            "/api/v1/workspaces/1/leads/{lead_id}/score",
            None,
            "leads:read",
        ),
        (
            "lead_scoring_routes",
            "get",
            "/api/v1/workspaces/1/leads/{lead_id}/score/history",
            None,
            "leads:read",
        ),
        (
            "lead_scoring_routes",
            "put",
            "/api/v1/workspaces/1/icp",
            {},
            "leads:write",
        ),
        # outbound_routes — leads:read ×2, leads:write ×1
        (
            "outbound_routes",
            "post",
            "/api/v1/workspaces/1/leads/{lead_id}/zalo-draft",
            None,
            "leads:read",
        ),
        (
            "outbound_routes",
            "post",
            "/api/v1/workspaces/1/leads/{lead_id}/zns-send",
            {"template_id": "t1", "template_data": {}},
            "leads:write",
        ),
        (
            "outbound_routes",
            "post",
            "/api/v1/workspaces/1/leads/{lead_id}/telegram-alert",
            None,
            "leads:read",
        ),
    ],
    ids=[
        "enrich_bulk",
        "enrich_cost",
        "enrich_single",
        "list_verified_contacts",
        "list_enrichment_requests",
        "score_leads",
        "list_lead_scores",
        "get_latest_lead_score",
        "get_lead_score_history",
        "update_icp_criteria",
        "generate_zalo_draft",
        "send_zns_message",
        "dispatch_telegram_alert",
    ],
)
def test_sweep_42_10_wrong_scope_403(
    monkeypatch: pytest.MonkeyPatch,
    router_name: str,
    method: str,
    path: str,
    json_body: dict | None,
    required_scope: str,
) -> None:
    """PAT sai scope → 403 'permission missing: <scope>' đúng từng endpoint 42-10."""
    import importlib

    router = importlib.import_module(f"app.routes.{router_name}").router
    wrong_scopes = (
        ["leads:read"] if required_scope == "leads:write" else ["leads:write"]
    )
    client = _build_router_client(
        monkeypatch, router, _pat_auth(scopes=wrong_scopes, workspace_id=1)
    )

    url = path.replace("{lead_id}", str(uuid4()))
    kwargs: dict[str, Any] = {}
    if json_body is not None:
        kwargs["json"] = json_body
    response = client.request(method, url, **kwargs)

    assert response.status_code == 403
    assert f"permission missing: {required_scope}" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Spec 42-11 — PAT scope sweep trên dnc_routes + lead_pipeline_routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "router_name,method,path,json_body,required_scope",
    [
        # dnc_routes — leads:read ×1, leads:write ×3
        (
            "dnc_routes",
            "get",
            "/api/v1/workspaces/1/dnc",
            None,
            "leads:read",
        ),
        (
            "dnc_routes",
            "post",
            "/api/v1/workspaces/1/dnc",
            {"record_type": "phone", "value": "0901234567"},
            "leads:write",
        ),
        (
            "dnc_routes",
            "delete",
            "/api/v1/workspaces/1/dnc/{record_id}",
            None,
            "leads:write",
        ),
        # lead_pipeline_routes — leads:read ×3, leads:write ×4
        (
            "lead_pipeline_routes",
            "get",
            "/api/v1/workspaces/1/leads/pipeline/stages",
            None,
            "leads:read",
        ),
        (
            "lead_pipeline_routes",
            "get",
            "/api/v1/workspaces/1/leads/{lead_id}/timeline",
            None,
            "leads:read",
        ),
        (
            "lead_pipeline_routes",
            "get",
            "/api/v1/workspaces/1/leads/{lead_id}/meeting/slots",
            None,
            "leads:read",
        ),
        (
            "lead_pipeline_routes",
            "post",
            "/api/v1/workspaces/1/leads/pipeline/stages",
            {"name": "Mới", "slug": "new-stage", "position": 9},
            "leads:write",
        ),
        (
            "lead_pipeline_routes",
            "patch",
            "/api/v1/workspaces/1/leads/{lead_id}/stage",
            {"stage_id": str(uuid4()), "expected_version": 1},
            "leads:write",
        ),
        (
            "lead_pipeline_routes",
            "post",
            "/api/v1/workspaces/1/leads/assign-batch",
            {"lead_ids": [str(uuid4())]},
            "leads:write",
        ),
        (
            "lead_pipeline_routes",
            "post",
            "/api/v1/workspaces/1/leads/{lead_id}/meeting/book",
            {"start": "2026-12-01T09:00:00+07:00", "duration_minutes": 30},
            "leads:write",
        ),
        (
            "dnc_routes",
            "post",
            "/api/v1/workspaces/1/dnc/import-csv",
            None,
            "leads:write",
        ),
    ],
    ids=[
        "list_dnc_records",
        "create_dnc_record",
        "delete_dnc_record",
        "list_pipeline_stages",
        "list_lead_timeline",
        "list_meeting_slots",
        "create_pipeline_stage",
        "transition_lead_stage",
        "assign_leads_batch",
        "book_meeting_for_lead",
        "import_dnc_csv",
    ],
)
def test_sweep_42_11_wrong_scope_403(
    monkeypatch: pytest.MonkeyPatch,
    router_name: str,
    method: str,
    path: str,
    json_body: dict | None,
    required_scope: str,
) -> None:
    """PAT sai scope → 403 'permission missing: <scope>' đúng từng endpoint 42-11."""
    import importlib

    router = importlib.import_module(f"app.routes.{router_name}").router
    wrong_scopes = (
        ["leads:read"] if required_scope == "leads:write" else ["leads:write"]
    )
    client = _build_router_client(
        monkeypatch, router, _pat_auth(scopes=wrong_scopes, workspace_id=1)
    )

    url = path.replace("{lead_id}", str(uuid4())).replace(
        "{record_id}", str(uuid4())
    )
    kwargs: dict[str, Any] = {}
    if json_body is not None:
        kwargs["json"] = json_body
    response = client.request(method, url, **kwargs)

    assert response.status_code == 403
    assert f"permission missing: {required_scope}" in response.json()["detail"]


@pytest.mark.parametrize(
    "router_name,path",
    [
        ("dnc_routes", "/api/v1/workspaces/1/dnc"),
        ("lead_pipeline_routes", "/api/v1/workspaces/1/leads/pipeline/stages"),
    ],
    ids=["dnc_wrong_workspace", "pipeline_wrong_workspace"],
)
def test_sweep_42_11_wrong_workspace_403(
    monkeypatch: pytest.MonkeyPatch, router_name: str, path: str
) -> None:
    """PAT bound ws 999 gọi endpoint 42-11 trên ws 1 → 403 'workspace_id outside pat scope'."""
    import importlib

    router = importlib.import_module(f"app.routes.{router_name}").router
    client = _build_router_client(
        monkeypatch, router, _pat_auth(scopes=["leads:read"], workspace_id=999)
    )
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["detail"] == "workspace_id outside pat scope"


def test_clipper_pat_respects_api_access_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT leads:clipper:write trên ws api_access_enabled=False → 403 api-access."""
    import app.routes.lead_clipper_routes as clipper_routes

    workspace = SimpleNamespace(id=1, api_access_enabled=False)
    client = _build_router_client(
        monkeypatch,
        clipper_routes.router,
        _pat_auth(scopes=["leads:clipper:write"], workspace_id=1),
        workspace=workspace,
    )
    response = client.post(
        "/api/v1/workspaces/1/leads/clip",
        json={
            "source_canonical_url": "https://example.com/post/1",
            "source_platform": "facebook",
        },
    )
    assert response.status_code == 403
    assert "api-access" in response.json()["detail"]


def test_clipper_session_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session auth clip_lead: qua check_permission như cũ, không bị PAT gate."""
    import app.routes.lead_clipper_routes as clipper_routes

    async def _mock_perm(*args: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(is_owner=True, role=None, user_id=uuid4())

    # clipper import check_permission trực tiếp vào module namespace
    monkeypatch.setattr(clipper_routes, "check_permission", _mock_perm)

    existing_lead = SimpleNamespace(id=uuid4(), workspace_id=1)
    client = _build_router_client(
        monkeypatch,
        clipper_routes.router,
        AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True)),
        workspace=existing_lead,
    )
    # _find_duplicate_lead trả existing lead → early return 200 is_duplicate
    response = client.post(
        "/api/v1/workspaces/1/leads/clip",
        json={
            "source_canonical_url": "https://example.com/post/1",
            "source_platform": "facebook",
        },
    )
    assert response.status_code == 200
    assert response.json()["is_duplicate"] is True


def test_mint_legacy_unknown_scope_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI-42.7: legacy PAT với scope không thuộc catalog → 400 unknown scopes."""
    import app.routes.personal_access_tokens_routes as pat_routes

    client = _build_router_client(
        monkeypatch,
        pat_routes.router,
        AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True)),
    )
    response = client.post(
        "/api/v1/pats",
        json={"label": "bad-scope", "token_kind": "legacy", "scopes": ["bogus:scope"]},
    )
    assert response.status_code == 400
    assert "unknown scopes" in response.json()["detail"]


def test_mint_legacy_known_scope_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI-42.7: legacy PAT với leads:* scope hợp lệ → mint 200, scopes lưu đúng."""
    import app.routes.personal_access_tokens_routes as pat_routes

    client = _build_router_client(
        monkeypatch,
        pat_routes.router,
        AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True)),
    )
    response = client.post(
        "/api/v1/pats",
        json={
            "label": "lead-bot",
            "token_kind": "legacy",
            "scopes": ["leads:read", "leads:write"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scopes"] == ["leads:read", "leads:write"]


def test_mint_self_host_wipes_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """self_host PAT: scopes truyền vào bị wipe về [] — không cần validate."""
    import app.routes.personal_access_tokens_routes as pat_routes

    client = _build_router_client(
        monkeypatch,
        pat_routes.router,
        AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True)),
    )
    response = client.post(
        "/api/v1/pats",
        json={
            "label": "self-host",
            "token_kind": "self_host",
            "scopes": ["bogus:whatever"],
        },
    )
    assert response.status_code == 200
    assert response.json()["scopes"] == []
