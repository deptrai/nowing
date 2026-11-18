"""Unit tests Epic 45.2 — GET /campaigns/{id}/leads (junction reader đầu tiên).

Item = ``LeadRead.model_dump`` merge ``lead_role``/``run_id``/``added_at``.
Fake session theo pattern ``test_campaign_crud_routes.py``.
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
from app.db import get_async_session
from app.routes.campaign_routes import router as campaign_router
from app.users import get_auth_context, require_session_context

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes (copy pattern test_campaign_crud_routes.py)
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows if rows is not None else ([value] if value is not None else [])

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(
        self,
        *,
        campaigns: list[Any] | None = None,
        execute_results: list[_FakeResult] | None = None,
    ) -> None:
        self._campaigns = campaigns or []
        self._execute_results = list(execute_results or [])
        self.executed_sql: list[str] = []

    def add(self, obj: Any) -> None:
        pass

    async def execute(self, _stmt: Any, _params: Any = None) -> _FakeResult:
        sql = str(_stmt)
        if "set_config" in sql:
            return _FakeResult(None, [])
        self.executed_sql.append(sql)
        if self._execute_results:
            return self._execute_results.pop(0)
        return _FakeResult(None, [])

    async def get(self, model: type, obj_id: Any) -> Any:
        for c in self._campaigns:
            if getattr(c, "id", None) == obj_id:
                return c
        return None

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass

    async def flush(self) -> None:
        pass


def _campaign(workspace_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Campaign",
        direction="demand",
        status="draft",
        input_payload={},
        created_at=datetime.now(UTC),
    )


def _lead(**overrides: Any) -> SimpleNamespace:
    """Lead tối thiểu đủ field required của LeadRead (còn lại dùng default)."""
    base: dict[str, Any] = {
        "id": uuid4(),
        "workspace_id": 10,
        "source": "enterprise",
        "company_name": "Công ty ABC",
        "created_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _campaign_lead(
    campaign: SimpleNamespace,
    lead: SimpleNamespace,
    *,
    role: str = "buyer",
    run_id: Any = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        campaign_id=campaign.id,
        lead_id=lead.id,
        workspace_id=campaign.workspace_id,
        role=role,
        run_id=run_id or uuid4(),
        created_at=datetime.now(UTC),
    )


def _fake_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(campaign_router)
    return test_app


def _client(app: FastAPI, session: _FakeSession) -> TestClient:
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[require_session_context] = _fake_auth
    app.dependency_overrides[get_auth_context] = _fake_auth
    return TestClient(app)


@pytest.fixture(autouse=True)
def _patch_auth_check():
    with patch(
        "app.dependencies.auth.check_permission", AsyncMock(return_value=None)
    ), patch(
        "app.routes.campaign_routes.check_permission", AsyncMock(return_value=None)
    ):
        yield


# ---------------------------------------------------------------------------
# Happy path — shape + merge junction fields
# ---------------------------------------------------------------------------


def test_list_campaign_leads_shape_and_merge(app: FastAPI):
    """DETAIL_OK + LEADS_ROLE: item = LeadRead fields + lead_role/run_id/added_at."""
    campaign = _campaign()
    lead = _lead(company_name="Nhà cung cấp XYZ")
    junction = _campaign_lead(campaign, lead, role="supplier")
    # execute tuần tự: count → rows [(campaign_lead, lead)].
    session = _FakeSession(
        campaigns=[campaign],
        execute_results=[
            _FakeResult(1),
            _FakeResult(None, [(junction, lead)]),
        ],
    )
    client = _client(app, session)

    res = client.get(f"/workspaces/10/campaigns/{campaign.id}/leads")
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["total"] == 1
    assert body["limit"] == 20
    assert body["offset"] == 0

    item = body["items"][0]
    # Junction fields merge lên LeadRead.
    assert item["lead_role"] == "supplier"
    assert item["run_id"] == str(junction.run_id)
    assert item["added_at"] == junction.created_at.isoformat()
    # LeadRead fields.
    assert item["id"] == str(lead.id)
    assert item["company_name"] == "Nhà cung cấp XYZ"
    assert item["source"] == "enterprise"
    assert item["workspace_id"] == 10


def test_list_campaign_leads_run_id_nullable(app: FastAPI):
    """Junction không gắn run (run_id NULL) → item.run_id = None."""
    campaign = _campaign()
    lead = _lead()
    junction = _campaign_lead(campaign, lead, run_id=None)
    junction.run_id = None
    session = _FakeSession(
        campaigns=[campaign],
        execute_results=[_FakeResult(1), _FakeResult(None, [(junction, lead)])],
    )
    client = _client(app, session)

    res = client.get(f"/workspaces/10/campaigns/{campaign.id}/leads")
    assert res.status_code == 200, res.text
    assert res.json()["items"][0]["run_id"] is None


def test_list_campaign_leads_empty(app: FastAPI):
    """LEADS_EMPTY: 0 junction → items=[], total=0."""
    campaign = _campaign()
    session = _FakeSession(
        campaigns=[campaign],
        execute_results=[_FakeResult(0), _FakeResult(None, [])],
    )
    client = _client(app, session)

    res = client.get(f"/workspaces/10/campaigns/{campaign.id}/leads")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_campaign_leads_pagination_offset(app: FastAPI):
    """RUNS_PAGED tương đương: page=2&page_size=1 → offset=1, limit=1."""
    campaign = _campaign()
    lead = _lead()
    junction = _campaign_lead(campaign, lead)
    session = _FakeSession(
        campaigns=[campaign],
        execute_results=[_FakeResult(3), _FakeResult(None, [(junction, lead)])],
    )
    client = _client(app, session)

    res = client.get(
        f"/workspaces/10/campaigns/{campaign.id}/leads?page=2&page_size=1"
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert body["total"] == 3
    assert len(body["items"]) == 1


def test_list_campaign_leads_page_size_cap_422(app: FastAPI):
    campaign = _campaign()
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    res = client.get(
        f"/workspaces/10/campaigns/{campaign.id}/leads?page_size=500"
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 404 / workspace isolation
# ---------------------------------------------------------------------------


def test_list_campaign_leads_not_found(app: FastAPI):
    """DETAIL_404: campaign_id không tồn tại → 404."""
    session = _FakeSession()
    client = _client(app, session)
    res = client.get(f"/workspaces/10/campaigns/{uuid4()}/leads")
    assert res.status_code == 404


def test_list_campaign_leads_invalid_uuid_404(app: FastAPI):
    session = _FakeSession()
    client = _client(app, session)
    res = client.get("/workspaces/10/campaigns/not-a-uuid/leads")
    assert res.status_code == 404


def test_list_campaign_leads_wrong_workspace_404(app: FastAPI):
    """CROSS_WS: campaign thuộc workspace khác → 404 (workspace filter)."""
    campaign = _campaign(workspace_id=99)
    session = _FakeSession(campaigns=[campaign])
    client = _client(app, session)
    res = client.get(f"/workspaces/10/campaigns/{campaign.id}/leads")
    assert res.status_code == 404
