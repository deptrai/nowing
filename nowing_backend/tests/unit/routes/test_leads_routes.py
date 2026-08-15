"""Unit tests for Lead Intelligence Panel and Company Graph routes (Story 21.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import Lead, VerifiedContact, Workspace, get_async_session
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
        leads: list[Any] | None = None,
        contacts: list[Any] | None = None,
        workspace: Any = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = False
        self._leads = leads or []
        self._contacts = contacts or []
        self._workspace = workspace or SimpleNamespace(id=1, name="Test Workspace")

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any) -> _FakeResult:
        stmt_str = str(stmt)
        if "count" in stmt_str.lower():
            return _FakeResult(value=len(self._leads))
        if "verified_contacts" in stmt_str.lower():
            return _FakeResult(rows=self._contacts)
        if "leads.id =" in stmt_str:
            return _FakeResult(value=self._leads[0] if self._leads else None)
        return _FakeResult(rows=self._leads)

    async def get(self, model: type, ident: Any) -> Any:
        if model is Workspace:
            return self._workspace
        if model is Lead:
            return self._leads[0] if self._leads else None
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        pass


def _create_mock_lead(
    *,
    lead_id: UUID | None = None,
    workspace_id: int = 1,
    source: str = "facebook",
    company_name: str = "VNG Corporation",
    fit_score: float = 92.0,
    status: str = "new",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=lead_id or uuid4(),
        workspace_id=workspace_id,
        client_id=None,
        source=source,
        source_url="https://facebook.com/post/123",
        source_chunk_id=None,
        company_name=company_name,
        domain="vng.com.vn",
        industry="Software",
        company_size="2000-5000",
        location="TP. Hồ Chí Minh",
        tech_stack=["Python", "React", "PostgreSQL"],
        fit_score=fit_score,
        intent_score=88.0,
        composite_score=fit_score,
        status=status,
        enriched=True,
        consent_status="granted",
        legal_basis="legitimate_interest",
        created_at=datetime.now(UTC),
        updated_at=None,
        verified_contacts=[
            SimpleNamespace(
                id=uuid4(),
                name="Lê Hồng Minh",
                title="Founder & CEO",
                email="minh.le@vng.com.vn",
                phone="0912.345.678",
                confidence=0.98,
            )
        ],
    )


def _fake_auth() -> AuthContext:
    return AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True))


@pytest.fixture
def mock_leads():
    return [
        _create_mock_lead(company_name="VNG Corporation", source="facebook", fit_score=92.0),
        _create_mock_lead(company_name="FPT Software", source="topcv", fit_score=85.0),
    ]


@pytest.fixture
def client(monkeypatch, mock_leads):
    import app.routes.leads_routes as leads_routes

    async def _mock_check_perm(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(leads_routes, "check_permission", _mock_check_perm)

    from app.routes.leads_routes import router

    fake_session = _FakeSession(leads=mock_leads)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_async_session] = lambda: fake_session
    app.dependency_overrides[get_auth_context] = _fake_auth

    return TestClient(app)


def test_list_leads_returns_paginated_response(client, mock_leads):
    response = client.get("/workspaces/1/leads")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 2
    first_item = data["items"][0]
    assert first_item["company_name"] == "VNG Corporation"
    assert first_item["fit_score"] == 92.0
    assert first_item["phone"] == "0912.345.678"
    assert first_item["intent"] == "BÁN"


def test_list_leads_with_filters(client):
    response = client.get("/workspaces/1/leads?source=facebook&status=new&min_score=80")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_get_lead_detail(client, mock_leads):
    lead_id = mock_leads[0].id
    response = client.get(f"/workspaces/1/leads/{lead_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "VNG Corporation"
    assert data["phone"] == "0912.345.678"


def test_update_lead_status_success(client, mock_leads):
    lead_id = mock_leads[0].id
    response = client.patch(
        f"/workspaces/1/leads/{lead_id}/status",
        json={"status": "qualified"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "qualified"


def test_update_lead_status_invalid_value(client, mock_leads):
    lead_id = mock_leads[0].id
    response = client.patch(
        f"/workspaces/1/leads/{lead_id}/status",
        json={"status": "invalid_status_enum"},
    )
    assert response.status_code == 422


def test_get_company_graph(client):
    response = client.get("/workspaces/1/companies/VNG%20Corporation/graph")
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "VNG Corporation"
    assert "legal_entity" in data
    assert data["legal_entity"]["tax_id"] == "0102938475"
    assert len(data["decision_makers"]) >= 1
    assert data["decision_makers"][0]["name"] == "Lê Hồng Minh"
    assert len(data["tenders"]) >= 1
    assert data["tenders"][0]["tender_number"] == "IB2400198273"
    assert len(data["hiring_signals"]) >= 1
    assert data["hiring_velocity_pct"] == 65.0
    assert data["active_jobs_count"] == 48


def test_company_graph_empty_name_returns_400(client):
    response = client.get("/workspaces/1/companies/%20%20/graph")
    assert response.status_code == 400
