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
from app.db import Workspace, get_async_session
from app.rate_limiter import limiter

pytestmark = pytest.mark.unit


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Test client for the lead-batch router with mocked service and auth."""
    monkeypatch.setattr(
        lead_batch_routes, "check_permission", AsyncMock(return_value=None)
    )

    async def _mock_ingest(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "ingested_count": 1,
            "skipped_blacklisted_count": 0,
            "failed_count": 0,
            "execution_time_ms": 1.0,
            "lead_ids": [uuid4()],
        }

    monkeypatch.setattr(
        lead_batch_routes.LeadBatchService, "ingest_batch", AsyncMock(side_effect=_mock_ingest)
    )

    class _FakeSession:
        async def get(self, model: type, ident: Any) -> Any | None:
            if model is Workspace:
                return SimpleNamespace(id=ident)
            return None

        async def execute(self, _stmt: Any, _params: Any | None = None) -> Any:
            class _Result:
                pass

            return _Result()

        async def commit(self) -> None:
            pass

        async def flush(self) -> None:
            pass

    async def _fake_session():
        yield _FakeSession()

    user = SimpleNamespace(id=uuid4(), is_active=True)

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(lead_batch_routes.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    app.dependency_overrides[lead_batch_routes.get_auth_context] = (
        lambda: AuthContext.session(user)
    )

    return TestClient(app)


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
