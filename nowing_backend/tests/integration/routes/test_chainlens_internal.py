"""Integration tests for chainlens-research service-to-service callbacks."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.db import (
    Chunk,
    Document,
    DocumentType,
    SearchSourceConnector,
    TokenUsage,
    User,
    Workspace,
    WorkspaceMembership,
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
async def test_private_data_search_callback_records_token_usage(
    chainlens_internal_client,
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """A successful private search writes a TokenUsage row with cost_micros=0."""
    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={"query": "irrelevant", "workspaceId": db_workspace.id},
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(TokenUsage)
        .where(
            TokenUsage.workspace_id == db_workspace.id,
            TokenUsage.usage_type == "chainlens_private_search",
        )
        .order_by(TokenUsage.id.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.cost_micros == 0
    assert record.user_id == db_workspace.user_id


@pytest.mark.asyncio
async def test_private_data_search_callback_uses_requested_user_id_for_token_usage(
    chainlens_internal_client,
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """When userId is a workspace member, TokenUsage uses it instead of the owner."""
    from uuid import uuid4

    member = User(
        id=uuid4(),
        email="member@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(member)
    await db_session.flush()

    # Add the user as a workspace member; role can be None for this test.
    membership = WorkspaceMembership(
        user_id=member.id,
        workspace_id=db_workspace.id,
    )
    db_session.add(membership)
    await db_session.flush()

    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "irrelevant",
            "workspaceId": db_workspace.id,
            "userId": str(member.id),
        },
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(TokenUsage)
        .where(
            TokenUsage.workspace_id == db_workspace.id,
            TokenUsage.usage_type == "chainlens_private_search",
        )
        .order_by(TokenUsage.id.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.user_id == member.id


@pytest.mark.asyncio
async def test_private_data_search_callback_is_isolated_between_workspaces(
    chainlens_internal_client,
    db_session: AsyncSession,
    db_user,
    db_workspace: Workspace,
):
    """Results never include documents from a different workspace."""
    from uuid import uuid4

    from app.routes.workspaces_routes import create_default_roles_and_membership

    other_user = User(
        id=uuid4(),
        email="other@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.flush()

    other_workspace = Workspace(name="Other Space", user_id=other_user.id)
    db_session.add(other_workspace)
    await db_session.flush()
    await create_default_roles_and_membership(
        db_session, other_workspace.id, other_user.id
    )

    own_doc = Document(
        title="Own Doc",
        document_type=DocumentType.FILE,
        content="shared content",
        content_hash="hash-own",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    other_doc = Document(
        title="Other Doc",
        document_type=DocumentType.FILE,
        content="shared content",
        content_hash="hash-other",
        workspace_id=other_workspace.id,
        created_by_id=other_user.id,
    )
    db_session.add(own_doc)
    db_session.add(other_doc)
    await db_session.flush()

    own_chunk = Chunk(
        content="shared content chunk", position=0, document_id=own_doc.id
    )
    other_chunk = Chunk(
        content="shared content chunk", position=0, document_id=other_doc.id
    )
    db_session.add(own_chunk)
    db_session.add(other_chunk)
    await db_session.flush()

    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "shared content",
            "workspaceId": db_workspace.id,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["chunks"]) == 1
    assert body["chunks"][0]["metadata"]["document_id"] == own_doc.id


@pytest.mark.asyncio
async def test_private_data_search_callback_rejects_malformed_user_id(
    chainlens_internal_client,
    db_workspace: Workspace,
):
    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "irrelevant",
            "workspaceId": db_workspace.id,
            "userId": "not-a-uuid",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_private_data_search_callback_returns_validation_details(
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
    body = response.json()
    assert "error" in body
    assert any(err.get("loc", []) == ["query"] for err in body["error"]["fields"])


@pytest.mark.asyncio
async def test_private_data_search_callback_filters_by_sources(
    chainlens_internal_client,
    db_session: AsyncSession,
    db_user,
    db_workspace: Workspace,
):
    """The ``sources`` list maps to DocumentType and filters results."""
    file_doc = Document(
        title="File Doc",
        document_type=DocumentType.FILE,
        content="file content",
        content_hash="hash-file",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    note_doc = Document(
        title="Note Doc",
        document_type=DocumentType.NOTE,
        content="note content",
        content_hash="hash-note",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(file_doc)
    db_session.add(note_doc)
    await db_session.flush()

    file_chunk = Chunk(content="file chunk", position=0, document_id=file_doc.id)
    note_chunk = Chunk(content="note chunk", position=0, document_id=note_doc.id)
    db_session.add(file_chunk)
    db_session.add(note_chunk)
    await db_session.flush()

    response = await chainlens_internal_client.post(
        "/v1/private-data/search",
        json={
            "query": "chunk",
            "workspaceId": db_workspace.id,
            "sources": ["FILE"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["chunks"]) == 1
    assert body["chunks"][0]["metadata"]["document_id"] == file_doc.id


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
