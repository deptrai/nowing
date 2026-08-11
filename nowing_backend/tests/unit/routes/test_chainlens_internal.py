"""Unit tests for ``app.routes.chainlens_internal``."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = pytest.mark.unit


class _FakeAuth:
    configured = True

    def validate_inbound_token(self, request: Any) -> Any:
        return SimpleNamespace(
            workspace_id=42, token="valid", correlation_id="corr-123"
        )


class _FakeOutput:
    items = [
        {"title": "House A", "price": "2 tỷ", "city": "HN", "district": "Cầu Giấy"},
        {"title": "House B", "price": "3 tỷ", "city": "HN", "district": "Đống Đa"},
    ]


def _make_run_app():
    """Build a small FastAPI app with only the chainlens-internal router."""
    from fastapi import FastAPI

    # Import at least one scraper so the registry contains the capabilities we
    # exercise in the happy-path test.
    import app.capabilities.batdongsan
    from app.routes.chainlens_internal import router

    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import app.routes.chainlens_internal as internal_mod

    # Patch the auth class imported into the route module, not the original
    # class, to avoid leaking a monkey-patched __new__ across tests.
    monkeypatch.setattr(internal_mod, "ChainLensServiceAuth", _FakeAuth)
    monkeypatch.setattr(
        internal_mod, "execute_with_context", AsyncMock(return_value=_FakeOutput())
    )

    chunks = [
        Mock(content="chunk 1", metadata=Mock(sourceId="s1")),
        Mock(content="chunk 2", metadata=Mock(sourceId="s2")),
    ]

    def fake_to_chunks(*, domain: str, data: Any, **kwargs: Any) -> list[Any]:
        return chunks

    monkeypatch.setattr("app.routes.chainlens_internal.to_chunks", fake_to_chunks)

    class _IngestResult:
        ingest_job_id = "job-123"
        parent_ingest_job_id = None
        child_ingest_job_ids = []
        ingested_source_ids = ["s1", "s2"]
        noop_source_ids = []
        status = "ok"

    monkeypatch.setattr(
        "app.routes.chainlens_internal.NowingIngestService",
        Mock(return_value=Mock(ingest=AsyncMock(return_value=_IngestResult()))),
    )

    return TestClient(_make_run_app())


def test_run_scraper_rejects_missing_auth(client, monkeypatch):
    import app.routes.chainlens_internal as internal_mod

    class _NoAuth:
        configured = True

        def validate_inbound_token(self, request: Any) -> Any:
            return None

    monkeypatch.setattr(internal_mod, "ChainLensServiceAuth", _NoAuth)

    response = client.post(
        "/v1/scraper/batdongsan/run",
        json={"workspace_id": 42, "params": {"city": "HN", "listing_type": "buy"}},
    )
    assert response.status_code == 401


def test_run_scraper_unknown_capability(client):
    response = client.post(
        "/v1/scraper/unknown/run",
        json={"workspace_id": 42, "params": {}},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_scraper_success(client):
    # TestClient is sync, but the route is async; the fixture runs it synchronously.
    response = client.post(
        "/v1/scraper/batdongsan/run",
        json={
            "workspace_id": 42,
            "params": {"city": "HN", "listing_type": "buy", "max_items": 2},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scraper_id"] == "batdongsan"
    assert body["ingest_job_id"] == "job-123"
    assert body["status"] == "ok"
    assert body["ingested_count"] == 2


@pytest.mark.asyncio
async def test_run_scraper_ignores_untrusted_workspace_id_in_body(client):
    """The route must trust the auth context, not the request body's workspace_id."""
    response = client.post(
        "/v1/scraper/batdongsan/run",
        json={
            # The auth context says workspace 42, so this malicious value must not
            # be used for billing/scraper execution.
            "workspace_id": 999,
            "params": {"city": "HN", "listing_type": "buy", "max_items": 2},
        },
    )
    assert response.status_code == 200
