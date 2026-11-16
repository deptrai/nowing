"""Red-phase ATDD unit tests for Story 26.1 batch lead ingestion routes.

Tests focus on AC-1: POST /api/v1/workspaces/:workspace_id/leads/batch-ingest
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
from app.db import LeadActivityLog, Workspace, get_async_session
from app.rate_limiter import limiter
from app.services.lead_batch_service import LeadItemValidationError

pytestmark = pytest.mark.unit


def _build_client(monkeypatch: pytest.MonkeyPatch, auth: AuthContext) -> TestClient:
    """Test client for the lead-batch router with mocked service and auth."""
    monkeypatch.setattr(
        "app.dependencies.auth.check_permission", AsyncMock(return_value=None)
    )

    async def _mock_ingest(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "ingested_count": 1,
            "skipped_blacklisted_count": 0,
            "failed_count": 0,
            "execution_time_ms": 1.0,
            "lead_ids": [uuid4()],
            "accepted_lead_ids": [uuid4()],
        }

    monkeypatch.setattr(
        lead_batch_routes.LeadBatchService, "ingest_batch", AsyncMock(side_effect=_mock_ingest)
    )

    class _FakeSession:
        def __init__(self) -> None:
            self.added: list[Any] = []
            self.rolled_back = False

        async def get(self, model: type, ident: Any) -> Any | None:
            if model is Workspace:
                return SimpleNamespace(id=ident)
            return None

        async def execute(self, _stmt: Any, _params: Any | None = None) -> Any:
            class _Result:
                pass

            return _Result()

        def add(self, obj: Any) -> None:
            self.added.append(obj)

        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            self.rolled_back = True

        async def flush(self) -> None:
            pass

    fake_session = _FakeSession()

    async def _fake_session():
        yield fake_session

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(lead_batch_routes.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[lead_batch_routes.get_auth_context] = lambda: auth

    client = TestClient(app)
    client.fake_session = fake_session  # type: ignore[attr-defined]
    return client


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Session-authenticated test client."""
    return _build_client(monkeypatch, AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True)))


def test_batch_ingest_route_exists(client: TestClient) -> None:
    """should mount POST /api/v1/workspaces/{workspace_id}/leads/batch-ingest and return 200 for valid payload."""
    client_ip = str(uuid4())
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": client_ip},
        json={"leads": [{"domain": "example.com"}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ingested_count"] == 1
    assert data["failed_count"] == 0
    assert "lead_ids" in data


def test_batch_ingest_route_rejects_empty_leads(client: TestClient) -> None:
    """should return 422 when leads array is empty."""
    client_ip = str(uuid4())
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": client_ip},
        json={"leads": []},
    )
    assert response.status_code == 422


def test_batch_ingest_route_enforces_rate_limit(client: TestClient) -> None:
    """should return 429 after 31 batches in one minute for the same workspace."""
    client_ip = str(uuid4())
    payload = {"leads": [{"domain": "example.com"}]}

    for _ in range(30):
        response = client.post(
            "/api/v1/workspaces/1/leads/batch-ingest",
            headers={"X-Forwarded-For": client_ip},
            json=payload,
        )
        assert response.status_code == 200

    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": client_ip},
        json=payload,
    )
    assert response.status_code == 429


def test_batch_ingest_route_returns_summary_not_pii(client: TestClient) -> None:
    """should return summary counts without phone, email, or value_hmac."""
    client_ip = str(uuid4())
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": client_ip},
        json={
            "leads": [
                {
                    "phone": "+1234567890",
                    "email": "a@example.com",
                    "domain": "example.com",
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ingested_count"] == 1
    assert "phone" not in data
    assert "email" not in data
    assert "value_hmac" not in data
    assert "lead_ids" in data


# ---------------------------------------------------------------------------
# PAT scope enforcement (AD-2)
# ---------------------------------------------------------------------------


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


def test_pat_without_leads_write_scope_gets_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """PAT missing leads:write (including legacy scopes=[]) is fail-closed 403."""
    client = _build_client(monkeypatch, _pat_auth(scopes=[], workspace_id=1))
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": str(uuid4())},
        json={"leads": [{"domain": "example.com"}]},
    )
    assert response.status_code == 403
    assert "leads:write" in response.json()["detail"]


def test_pat_bound_to_other_workspace_gets_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT bound to workspace A cannot write workspace B."""
    client = _build_client(monkeypatch, _pat_auth(scopes=["leads:write"], workspace_id=999))
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": str(uuid4())},
        json={"leads": [{"domain": "example.com"}]},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "workspace_id outside pat scope"


def test_pat_with_scope_and_matching_workspace_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT_OK: 200 plus a lead_activity_logs row carrying PAT attribution."""
    client = _build_client(monkeypatch, _pat_auth(scopes=["leads:write"], workspace_id=1))
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": str(uuid4()), "Idempotency-Key": "idem-123"},
        json={"leads": [{"domain": "example.com"}]},
    )
    assert response.status_code == 200
    logs = [
        row
        for row in client.fake_session.added  # type: ignore[attr-defined]
        if isinstance(row, LeadActivityLog)
    ]
    assert len(logs) == 1
    assert logs[0].details["actor_pat_token_id"] == 77
    assert logs[0].details["idempotency_key"] == "idem-123"


def test_pat_with_unbound_workspace_and_scope_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PAT with workspace_id=None (unbound) + leads:write may ingest anywhere."""
    client = _build_client(
        monkeypatch, _pat_auth(scopes=["leads:write"], workspace_id=None)
    )
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": str(uuid4())},
        json={"leads": [{"domain": "example.com"}]},
    )
    assert response.status_code == 200


def test_session_caller_writes_no_activity_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session callers keep the previous log-free behavior."""
    client = _build_client(
        monkeypatch, AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True))
    )
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": str(uuid4())},
        json={"leads": [{"domain": "example.com"}]},
    )
    assert response.status_code == 200
    assert not [
        row
        for row in client.fake_session.added  # type: ignore[attr-defined]
        if isinstance(row, LeadActivityLog)
    ]


# ---------------------------------------------------------------------------
# Structured 422 reject-all
# ---------------------------------------------------------------------------


def test_degenerate_batch_returns_structured_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """422 body carries status/rejected_indexes/reason_map and rolls back."""
    client = _build_client(
        monkeypatch, AuthContext.session(SimpleNamespace(id=uuid4(), is_active=True))
    )
    monkeypatch.setattr(
        lead_batch_routes.LeadBatchService,
        "ingest_batch",
        AsyncMock(
            side_effect=LeadItemValidationError(
                "Batch rejected: 2 degenerate lead(s) at indexes [1, 3]",
                rejected_indexes=[1, 3],
                reason_map={1: "degenerate", 3: "degenerate"},
            )
        ),
    )
    response = client.post(
        "/api/v1/workspaces/1/leads/batch-ingest",
        headers={"X-Forwarded-For": str(uuid4())},
        json={"leads": [{"domain": "a.com"}, {}, {"domain": "b.com"}, {}]},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "failed"
    assert body["rejected_indexes"] == [1, 3]
    assert set(body["reason_map"]) == {"1", "3"}
    assert client.fake_session.rolled_back is True  # type: ignore[attr-defined]
