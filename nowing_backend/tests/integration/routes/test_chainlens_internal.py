"""Integration tests for chainlens-research service-to-service callbacks."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.db import (
    Chunk,
    Document,
    DocumentType,
    SearchSourceConnector,
    Workspace,
    get_async_session,
)
from app.routes.chainlens_internal import chainlens_auth_dependency
from app.services.chainlens.auth import ChainLensAuthContext, get_chainlens_auth

pytestmark = [pytest.mark.integration]

limiter.enabled = False


@pytest_asyncio.fixture
async def chainlens_internal_client(
    db_session: AsyncSession,
    db_user,
    db_workspace: Workspace,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client with service auth overridden and DB session wired."""

    async def _valid_auth() -> ChainLensAuthContext:
        return ChainLensAuthContext(
            workspace_id=db_workspace.id,
            correlation_id="corr-test",
            token="test-token",
        )

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[chainlens_auth_dependency] = _valid_auth
    app.dependency_overrides[get_async_session] = _override_session
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def chainlens_auth_client(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client that exercises the real service-token auth dependency."""
    import app.services.chainlens.auth as auth_mod

    fake_config = type(
        "Config",
        (),
        {
            "CHAINLENS_SERVICE_TOKEN": "valid-token",
            "CHAINLENS_API_KEY": "",
        },
    )()
    monkeypatch.setattr(auth_mod, "config", fake_config)
    get_chainlens_auth.cache_clear()

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.pop(chainlens_auth_dependency, None)
    app.dependency_overrides[get_async_session] = _override_session
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
        ) as client:
            client._chainlens_workspace_id = db_workspace.id  # type: ignore[attr-defined]
            yield client
    finally:
        get_chainlens_auth.cache_clear()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.mark.asyncio
async def test_scraper_run_callback_returns_accepted(chainlens_internal_client):
    response = await chainlens_internal_client.post("/v1/scraper/batdongsan/run")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["scraper_id"] == "batdongsan"


@pytest.mark.asyncio
async def test_private_data_search_callback_returns_empty(
    chainlens_internal_client,
    db_workspace: Workspace,
):
    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "something not in the workspace",
            "workspaceId": db_workspace.id,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chunks"] == []
    assert body["costDollars"] == 0.0


@pytest.mark.asyncio
async def test_private_data_search_callback_returns_private_chunks(
    chainlens_internal_client,
    db_session: AsyncSession,
    db_user,
    db_workspace: Workspace,
):
    """Indexed documents and chunks are returned as private_provider chunks."""
    document = Document(
        title="Private Test Document",
        document_type=DocumentType.FILE,
        content="Private test document content.",
        content_hash="hash-123",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(document)
    await db_session.flush()

    chunk = Chunk(
        content="matching chunk content",
        position=0,
        document_id=document.id,
    )
    db_session.add(chunk)
    await db_session.flush()

    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "matching chunk",
            "workspaceId": db_workspace.id,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["costDollars"] == 0.0
    assert len(body["chunks"]) > 0

    first = body["chunks"][0]
    assert first["metadata"]["source"] == "private_provider"
    assert first["metadata"]["document_id"] == document.id
    assert first["metadata"]["chunk_id"] == chunk.id
    assert first["metadata"]["workspace_id"] == db_workspace.id
    assert (
        f"nowing://documents/{document.id}/chunks/{chunk.id}"
        in first["metadata"]["sourceId"]
    )


@pytest.mark.asyncio
async def test_private_data_search_callback_rejects_workspace_mismatch(
    chainlens_internal_client,
    db_workspace: Workspace,
):
    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "irrelevant",
            "workspaceId": db_workspace.id + 9999,
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_private_data_search_callback_rejects_invalid_body(
    chainlens_internal_client,
    db_workspace: Workspace,
):
    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "",
            "workspaceId": db_workspace.id,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_private_data_search_callback_filters_by_connector(
    chainlens_internal_client,
    db_session: AsyncSession,
    db_user,
    db_workspace: Workspace,
    db_connector: SearchSourceConnector,
):
    """When connectorId is provided, only documents from that connector are returned."""
    from_document = Document(
        title="Connector Doc",
        document_type=DocumentType(db_connector.connector_type.value),
        content="connector content",
        content_hash="hash-c1",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        connector_id=db_connector.id,
    )
    other_document = Document(
        title="Other Doc",
        document_type=DocumentType.FILE,
        content="other content",
        content_hash="hash-c2",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(from_document)
    db_session.add(other_document)
    await db_session.flush()

    from_chunk = Chunk(
        content="connector matching chunk",
        position=0,
        document_id=from_document.id,
    )
    other_chunk = Chunk(
        content="other matching chunk",
        position=0,
        document_id=other_document.id,
    )
    db_session.add(from_chunk)
    db_session.add(other_chunk)
    await db_session.flush()

    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "matching chunk",
            "workspaceId": db_workspace.id,
            "connectorId": db_connector.id,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["chunks"]) == 1
    assert body["chunks"][0]["metadata"]["connector_id"] == db_connector.id


@pytest.mark.asyncio
async def test_scraper_run_callback_rejects_invalid_service_token(
    chainlens_auth_client,
):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={
            "Authorization": "Bearer wrong-token",
            "X-Workspace-Id": str(chainlens_auth_client._chainlens_workspace_id),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scraper_run_callback_accepts_valid_service_token(
    chainlens_auth_client,
):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={
            "Authorization": "Bearer valid-token",
            "X-Workspace-Id": str(chainlens_auth_client._chainlens_workspace_id),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"


@pytest.mark.asyncio
async def test_scraper_run_callback_rejects_missing_workspace_id(
    chainlens_auth_client,
):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scraper_run_callback_rejects_negative_workspace_id(
    chainlens_auth_client,
):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={
            "Authorization": "Bearer valid-token",
            "X-Workspace-Id": "-1",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scraper_run_callback_accepts_lowercase_bearer(chainlens_auth_client):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={
            "authorization": "bearer valid-token",
            "x-workspace-id": str(chainlens_auth_client._chainlens_workspace_id),
        },
    )
    assert response.status_code == 200
