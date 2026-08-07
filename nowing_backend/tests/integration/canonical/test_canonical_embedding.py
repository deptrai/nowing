"""Integration tests for canonical embedding backfill."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.canonical.tasks.backfill_canonical_embedding import (
    _backfill_canonical_embedding,
)
from app.db import CanonicalEntity, Workspace

pytestmark = [pytest.mark.integration, pytest.mark.canonical]


async def test_upsert_sets_embedding_pending_and_queues_task(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
):
    """Creating a canonical row leaves embedding_status='pending' and enqueues."""
    sent = []

    def _capture_apply_async(*, args, **kwargs):
        sent.append(args)

    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _capture_apply_async,
    )

    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="embed-f1",
        title="E",
        data={},
        search_text="e",
        source_name="batdongsan",
        source_record_id="e1",
    )

    assert entity.embedding_status == "pending"
    assert len(sent) == 1
    assert len(sent[0]) == 4
    assert sent[0][0] == str(entity.id)
    assert sent[0][1] == db_workspace.id
    assert sent[0][2] == entity.version


async def test_embedding_backfill_populates_vector(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
):
    """The backfill task embeds search_text and marks the row ready."""
    from app.config import config

    dim = config.embedding_model_instance.dimension
    monkeypatch.setattr(
        "app.canonical.tasks.backfill_canonical_embedding.embed_texts",
        lambda texts: [[0.2] * dim for _ in texts],
    )

    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="embed-f2",
        title="E2",
        data={},
        search_text="test content for embedding",
        source_name="batdongsan",
        source_record_id="e2",
    )
    await db_session.commit()

    await _backfill_canonical_embedding(
        str(entity.id),
        db_workspace.id,
        entity.version,
        config.EMBEDDING_MODEL or "test",
        session=db_session,
    )

    result = await db_session.scalar(
        select(CanonicalEntity).where(CanonicalEntity.id == entity.id)
    )
    assert result is not None
    assert result.embedding_status == "ready"
    assert result.embedding is not None
    assert len(result.embedding) == dim
    assert result.embedding_content_hash is not None
    assert result.embedding_model_name == (config.EMBEDDING_MODEL or "test")


async def test_embedding_backfill_skips_stale_version(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
):
    """The backfill task is idempotent: it skips if the version has moved on."""
    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="embed-f3",
        title="E3",
        data={},
        search_text="original",
        source_name="batdongsan",
        source_record_id="e3",
    )

    # Simulate a concurrent merge bumping the version before the task runs.
    entity.version = 2
    entity.search_text = "updated"
    entity.embedding_status = "pending"
    await db_session.commit()

    calls = []

    def _fake_embed(texts):
        calls.append(texts)
        return [[0.1] * 384]

    monkeypatch.setattr(
        "app.canonical.tasks.backfill_canonical_embedding.embed_texts", _fake_embed
    )

    await _backfill_canonical_embedding(
        str(entity.id), db_workspace.id, 1, "test", session=db_session
    )

    assert calls == []  # stale version, no embedding call
