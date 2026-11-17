"""Unit tests for lead table assign + export routes (Story 21.13).

Covers the three routes added for the multi-table tabs export flow:
POST /workspaces/{id}/tables/{table_id}/assign-leads,
POST /workspaces/{id}/leads/export (csv stream + async job),
GET  /workspaces/{id}/leads/export/jobs/{job_id}.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import (
    ExportJob,
    WorkspaceMembership,
    WorkspaceTable,
    get_async_session,
)
from app.routes.workspace_tables_routes import router
from app.users import get_auth_context

pytestmark = pytest.mark.unit

_WORKSPACE_ID = 1


class _FakeResult:
    def __init__(
        self,
        *,
        value: Any = None,
        rows: list[Any] | None = None,
        rowcount: int | None = None,
    ) -> None:
        self._value = value
        self._rows = rows or []
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """Minimal async session double that routes statements by table name."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.tables: dict[UUID, SimpleNamespace] = {}
        self.leads: list[SimpleNamespace] = []
        self.jobs: dict[UUID, ExportJob] = {}
        self.rowcount = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, ExportJob):
            obj.id = obj.id or uuid4()
            obj.created_at = obj.created_at or datetime.now(UTC)
            self.jobs[obj.id] = obj

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> _FakeResult:
        sql = str(stmt).lower()
        # "update leads" — note "updated_at" contains the substring "update",
        # so match the full "UPDATE leads" statement prefix instead.
        if "update leads" in sql:
            return _FakeResult(rowcount=self.rowcount)
        # The id-only query selects exactly `leads.id`; the full lead query
        # selects every column, so it must be matched first.
        if "select leads.id " in sql:
            return _FakeResult(rows=[lead.id for lead in self.leads])
        if "select" in sql and "leads" in sql:
            return _FakeResult(rows=self.leads)
        return _FakeResult()

    async def get(self, model: type, ident: Any) -> Any:
        if model is WorkspaceTable:
            return self.tables.get(ident)
        if model is ExportJob:
            return self.jobs.get(ident)
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        if isinstance(obj, ExportJob) and obj.id is None:
            obj.id = uuid4()


def _table(workspace_id: int = _WORKSPACE_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Hot leads",
        icon="table",
        filter_preset={},
        columns_config={},
        created_at=datetime.now(UTC),
        updated_at=None,
    )


def _lead(
    workspace_id: int = _WORKSPACE_ID, table_id: UUID | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        table_id=table_id,
        company_name="VNG Corporation",
        domain="vng.com.vn",
        source="facebook",
        industry="Software",
        location="TP. Hồ Chí Minh",
        fit_score=92.0,
        status="new",
        created_at=datetime.now(UTC),
        verified_contacts=[
            SimpleNamespace(
                name="Lê Hồng Minh",
                title="Founder",
                email="minh.le@vng.com.vn",
                phone="0912345678",
            )
        ],
    )


def _membership() -> WorkspaceMembership:
    return SimpleNamespace(workspace_id=_WORKSPACE_ID)  # type: ignore[return-value]


def _client(session: _FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext.session(
        SimpleNamespace(id=uuid4(), is_active=True)
    )
    # RequirePermission instances are per-route callables; override every
    # dependency that resolves a WorkspaceMembership so authz is not exercised.
    for route in app.routes:
        for dep in (
            getattr(route, "dependant", None) and route.dependant.dependencies
        ) or []:
            call = dep.call
            if getattr(call, "__class__", type).__name__ == "RequirePermission":
                app.dependency_overrides[call] = _membership
    return TestClient(app)


def test_assign_leads_updates_matching_rows() -> None:
    session = _FakeSession()
    table = _table()
    session.tables[table.id] = table
    lead_ids = [uuid4(), uuid4(), uuid4()]
    session.rowcount = 2

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/tables/{table.id}/assign-leads",
        json={"lead_ids": [str(lid) for lid in lead_ids]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assigned_count"] == 2
    assert body["table_id"] == str(table.id)
    assert session.committed is True


def test_assign_leads_empty_list_is_noop() -> None:
    session = _FakeSession()
    table = _table()
    session.tables[table.id] = table

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/tables/{table.id}/assign-leads",
        json={"lead_ids": []},
    )

    assert response.status_code == 200
    assert response.json()["assigned_count"] == 0
    assert session.committed is False


def test_assign_leads_unknown_table_returns_404() -> None:
    session = _FakeSession()

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/tables/{uuid4()}/assign-leads",
        json={"lead_ids": [str(uuid4())]},
    )

    assert response.status_code == 404
    assert session.committed is False


def test_assign_leads_rejects_foreign_workspace_table() -> None:
    session = _FakeSession()
    table = _table(workspace_id=999)
    session.tables[table.id] = table

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/tables/{table.id}/assign-leads",
        json={"lead_ids": [str(uuid4())]},
    )

    assert response.status_code == 404


def test_export_csv_streams_header_and_masked_contact() -> None:
    session = _FakeSession()
    session.leads = [_lead()]

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/leads/export",
        json={"export_type": "csv", "mask_pii": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("Company Name,Domain,Source")
    assert "VNG Corporation" in lines[1]
    # mask_pii must not leak the raw phone or email.
    assert "0912345678" not in response.text
    assert "minh.le@vng.com.vn" not in response.text
    assert session.added == []


def test_export_lark_creates_pending_job_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    lead = _lead()
    session.leads = [lead]
    dispatched: list[dict[str, Any]] = []

    class _Task:
        @staticmethod
        def delay(**kwargs: Any) -> None:
            dispatched.append(kwargs)

    monkeypatch.setattr(
        "app.tasks.lead_export_worker.run_lead_export_task", _Task, raising=False
    )

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/leads/export",
        json={
            "export_type": "lark_base",
            "lead_ids": [str(lead.id)],
            "target_config": {"app_token": "app", "table_id": "tbl"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["export_type"] == "lark_base"
    assert body["total_rows"] == 1
    assert body["job_id"]
    assert session.committed is True
    assert len(dispatched) == 1
    assert dispatched[0]["export_job_id"] == body["job_id"]
    assert dispatched[0]["lead_ids"] == [str(lead.id)]
    assert dispatched[0]["target_config"]["app_token"] == "app"


def test_export_survives_broker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()

    class _Task:
        @staticmethod
        def delay(**kwargs: Any) -> None:
            raise ConnectionError("broker down")

    monkeypatch.setattr(
        "app.tasks.lead_export_worker.run_lead_export_task", _Task, raising=False
    )

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/leads/export",
        json={"export_type": "share_link"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert len(session.jobs) == 1


def test_export_rejects_unknown_type() -> None:
    session = _FakeSession()

    response = _client(session).post(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/leads/export",
        json={"export_type": "pdf"},
    )

    assert response.status_code == 422


def test_get_export_job_returns_status() -> None:
    session = _FakeSession()
    job = ExportJob(
        workspace_id=_WORKSPACE_ID,
        export_type="lark_base",
        status="completed",
        total_rows=3,
        processed_rows=3,
        target_url="https://lark.example/base",
        config={},
    )
    session.add(job)

    response = _client(session).get(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/leads/export/jobs/{job.id}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["status"] == "completed"
    assert body["processed_rows"] == 3
    assert body["target_url"] == "https://lark.example/base"


def test_get_export_job_unknown_returns_404() -> None:
    session = _FakeSession()

    response = _client(session).get(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/leads/export/jobs/{uuid4()}"
    )

    assert response.status_code == 404


def test_get_export_job_rejects_foreign_workspace() -> None:
    session = _FakeSession()
    job = ExportJob(
        workspace_id=999,
        export_type="csv",
        status="pending",
        total_rows=0,
        processed_rows=0,
        config={},
    )
    session.add(job)

    response = _client(session).get(
        f"/api/v1/workspaces/{_WORKSPACE_ID}/leads/export/jobs/{job.id}"
    )

    assert response.status_code == 404
