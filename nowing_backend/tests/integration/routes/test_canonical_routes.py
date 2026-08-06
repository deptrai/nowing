"""Integration tests for canonical entity REST endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.db import (
    CanonicalEntity,
    CanonicalMergeHistory,
    Chunk,
    Document,
    DocumentType,
    User,
    Workspace,
)
from app.routes.workspaces_routes import create_default_roles_and_membership

pytestmark = pytest.mark.integration


def _no_op_apply_async(*args: Any, **kwargs: Any) -> None:
    """Prevent Celery broker round-trips in tests."""
    return None


@pytest.fixture(autouse=True)
def _patch_backfill(monkeypatch):
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )


@pytest.fixture(autouse=True)
def _patch_unified_search_embedding(monkeypatch):
    """Stub the unified search embedding call so route tests stay fast."""
    from app.canonical.services import unified_search_service
    from app.config import config as app_config

    dim = app_config.embedding_model_instance.dimension
    dummy = [0.1] * dim
    monkeypatch.setattr(
        unified_search_service.config.embedding_model_instance,
        "embed",
        lambda _text: dummy,
    )


@pytest_asyncio.fixture
async def _loaded_workspace(db_session: AsyncSession, db_user: User) -> Workspace:
    """A workspace with canonical entities and default roles for route tests."""
    space = Workspace(name="Canonical Route Space", user_id=db_user.id)
    db_session.add(space)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, space.id, db_user.id)

    await upsert_canonical_entity(
        db_session,
        workspace_id=space.id,
        entity_type="vn_bds.listing",
        fingerprint="route-f1",
        title="Nhà phố Quận 7",
        data={"price_value": 5_000_000_000, "area_value": 100.0},
        search_text="nha pho quan 7",
        source_name="batdongsan",
        source_record_id="route-1",
        source_snapshot={"title": "Nhà phố Quận 7"},
        conflict_flags=[{"type": "price_conflict", "field": "price_value"}],
    )
    await upsert_canonical_entity(
        db_session,
        workspace_id=space.id,
        entity_type="vn_bds.listing",
        fingerprint="route-f1",
        title="Nhà phố Quận 7 - mới",
        data={"price_value": 5_200_000_000, "area_value": 100.0},
        search_text="nha pho quan 7 moi",
        source_name="muaban",
        source_record_id="route-2",
        source_snapshot={"title": "Nhà phố Quận 7"},
        conflict_flags=[{"type": "price_conflict", "field": "price_value"}],
    )
    return space


async def test_list_canonical_entities(
    client_as_regular_user: httpx.AsyncClient,
    _loaded_workspace: Workspace,
):
    """GET /canonical-entities returns a paginated list for the workspace."""
    resp = await client_as_regular_user.get(
        f"/api/v1/canonical-entities?workspace_id={_loaded_workspace.id}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["workspace_id"] == _loaded_workspace.id
    assert item["entity_type"] == "vn_bds.listing"
    assert item["version"] == 2
    assert item["source_count"] == 2
    assert "fingerprint" not in item
    assert "search_text" not in item


async def test_list_canonical_entities_filter_by_conflict(
    client_as_regular_user: httpx.AsyncClient,
    _loaded_workspace: Workspace,
):
    """conflict=true filters to entities with non-empty conflict_flags."""
    resp = await client_as_regular_user.get(
        f"/api/v1/canonical-entities?workspace_id={_loaded_workspace.id}&conflict=true"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1

    resp = await client_as_regular_user.get(
        f"/api/v1/canonical-entities?workspace_id={_loaded_workspace.id}&conflict=false"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0


async def test_get_canonical_entity(
    client_as_regular_user: httpx.AsyncClient,
    _loaded_workspace: Workspace,
    db_session: AsyncSession,
):
    """GET /canonical-entities/{id} returns the entity, sources and latest history."""
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == _loaded_workspace.id
        )
    )
    assert entity is not None

    resp = await client_as_regular_user.get(f"/api/v1/canonical-entities/{entity.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(entity.id)
    assert body["workspace_id"] == _loaded_workspace.id
    assert body["canonical_data"]["price_value"] == 5_200_000_000
    assert body["source_count"] == 2
    assert len(body["sources"]) == 2
    assert body["latest_history"]["operation"] == "merge"
    assert body["latest_history"]["new_version"] == 2


async def test_get_canonical_entity_history(
    client_as_regular_user: httpx.AsyncClient,
    _loaded_workspace: Workspace,
    db_session: AsyncSession,
):
    """GET /canonical-entities/{id}/history returns the full audit trail."""
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == _loaded_workspace.id
        )
    )
    assert entity is not None

    resp = await client_as_regular_user.get(
        f"/api/v1/canonical-entities/{entity.id}/history"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["operation"] == "merge"
    assert body[1]["operation"] == "create"


async def test_revert_canonical_entity(
    client_as_regular_user: httpx.AsyncClient,
    _loaded_workspace: Workspace,
    db_session: AsyncSession,
):
    """POST /canonical-entities/{id}/revert restores a previous state."""
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == _loaded_workspace.id
        )
    )
    assert entity is not None

    history = await db_session.scalar(
        select(CanonicalMergeHistory)
        .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
        .order_by(CanonicalMergeHistory.created_at.desc())
    )
    assert history is not None
    assert history.operation == "merge"

    resp = await client_as_regular_user.post(
        f"/api/v1/canonical-entities/{entity.id}/revert",
        json={"history_id": str(history.id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 3
    assert body["canonical_data"] == {
        "price_value": 5_000_000_000,
        "area_value": 100.0,
    }
    assert body["latest_history"]["operation"] == "revert"


async def test_resolve_conflict(
    client_as_regular_user: httpx.AsyncClient,
    _loaded_workspace: Workspace,
    db_session: AsyncSession,
):
    """POST /canonical-entities/{id}/resolve-conflict updates data and records history."""
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == _loaded_workspace.id
        )
    )
    assert entity is not None

    resp = await client_as_regular_user.post(
        f"/api/v1/canonical-entities/{entity.id}/resolve-conflict",
        json={"field": "price_value", "value": 5_150_000_000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 3
    assert body["canonical_data"]["price_value"] == 5_150_000_000
    assert body["conflict_flags"] == []
    assert body["latest_history"]["operation"] == "resolve"


@pytest_asyncio.fixture
async def _loaded_unified_workspace(
    db_session: AsyncSession,
    db_user: User,
) -> Workspace:
    """Workspace with one canonical entity and one document for unified search."""
    from app.config import config as app_config

    space = Workspace(name="Unified Search Route Space", user_id=db_user.id)
    db_session.add(space)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, space.id, db_user.id)

    await upsert_canonical_entity(
        db_session,
        workspace_id=space.id,
        entity_type="vn_bds.listing",
        fingerprint="route-unified-f1",
        title="Nhà phố Quận 7",
        data={"price_value": 5_000_000_000, "area_value": 100.0},
        search_text="nha pho quan 7",
        source_name="batdongsan",
        source_record_id="route-unified-1",
        source_snapshot={"title": "Nhà phố Quận 7"},
        conflict_flags=[],
    )

    dim = app_config.embedding_model_instance.dimension
    dummy = [0.1] * dim
    doc = Document(
        title="Nhà phố giá rẻ",
        document_type=DocumentType.FILE,
        content="nha pho gia re quan 7",
        source_markdown="nha pho gia re quan 7",
        content_hash=f"content-{uuid.uuid4().hex[:12]}",
        unique_identifier_hash=f"uid-{uuid.uuid4().hex[:12]}",
        embedding=dummy,
        workspace_id=space.id,
        created_by_id=db_user.id,
        updated_at=datetime.now(UTC),
        status={"state": "ready"},
    )
    db_session.add(doc)
    await db_session.flush()

    chunk = Chunk(
        content="nha pho gia re quan 7",
        document_id=doc.id,
        embedding=dummy,
    )
    db_session.add(chunk)
    await db_session.flush()

    return space


async def test_unified_search_route(
    client_as_regular_user: httpx.AsyncClient,
    _loaded_unified_workspace: Workspace,
):
    """POST /canonical-search returns both canonical and document results."""
    resp = await client_as_regular_user.post(
        "/api/v1/canonical-search",
        json={
            "query": "nha pho",
            "workspace_id": _loaded_unified_workspace.id,
            "top_k": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    types = {item["type"] for item in body["items"]}
    assert "canonical_entity" in types
    assert "document" in types
