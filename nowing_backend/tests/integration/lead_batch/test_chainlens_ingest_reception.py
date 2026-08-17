"""Integration tests for Story 26.1 ChainLens -> Nowing chunk ingestion (AC-3, AC-4)."""

from __future__ import annotations

import hashlib
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import func, select

from app.db import ChainLensChunk, ChainLensIngestJob, Workspace

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_chainlens_ingest_persists_chunk_with_workspace_scoped_uuid(
    client,
    db_session,
    db_workspace,
    fake_embedding_model_1536,
    chainlens_headers,
):
    """Pattern 6: chunk id includes workspace_id and row is persisted."""
    source_url = "https://example.com/page"
    content = "ChainLens chunk content"
    idx = 0
    expected_id = uuid5(
        NAMESPACE_URL,
        f"{db_workspace.id}:{source_url}:{idx}:{hashlib.sha256(content.encode()).hexdigest()}",
    )

    payload = {
        "workspace_id": db_workspace.id,
        "scraper_id": "test.scraper",
        "run_id": "run-123",
        "chunks": [
            {"source_url": source_url, "content": content, "chunk_index": idx}
        ],
    }
    resp = await client.post(
        "/v1/chainlens/ingest",
        json=payload,
        headers=chainlens_headers(db_workspace.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_ingested_count"] == 1

    chunk = (
        await db_session.execute(
            select(ChainLensChunk).where(
                ChainLensChunk.id == expected_id,
                ChainLensChunk.workspace_id == db_workspace.id,
            )
        )
    ).scalar_one_or_none()
    assert chunk is not None
    assert chunk.content == content


@pytest.mark.asyncio
async def test_chainlens_ingest_per_workspace_uuid_no_collision(
    client,
    db_session,
    db_user,
    db_workspace,
    fake_embedding_model_1536,
    chainlens_headers,
):
    """Pattern 3/6: same URL across two workspaces creates two distinct chunk rows."""
    other_workspace = Workspace(
        name="Other",
        user_id=db_user.id,
        vertical="general",
        plan_tier="free",
    )
    db_session.add(other_workspace)
    await db_session.flush()

    source_url = "https://example.com/page"
    content = "same content"
    idx = 0

    for ws in (db_workspace, other_workspace):
        payload = {
            "workspace_id": ws.id,
            "scraper_id": "test.scraper",
            "run_id": "run-123",
            "chunks": [
                {"source_url": source_url, "content": content, "chunk_index": idx}
            ],
        }
        resp = await client.post(
            "/v1/chainlens/ingest",
            json=payload,
            headers=chainlens_headers(ws.id),
        )
        assert resp.status_code == 200

    count = (
        await db_session.execute(
            select(func.count(ChainLensChunk.id)).where(
                ChainLensChunk.source_url == source_url,
                ChainLensChunk.content == content,
            )
        )
    ).scalar_one()
    assert count == 2


@pytest.mark.asyncio
async def test_chainlens_ingest_rejects_invalid_token(client, db_workspace):
    """Pattern 2: invalid ChainLens auth token returns 401."""
    payload = {
        "workspace_id": db_workspace.id,
        "scraper_id": "x",
        "run_id": "r",
        "chunks": [],
    }
    resp = await client.post(
        "/v1/chainlens/ingest",
        json=payload,
        headers={
            "Authorization": "Bearer invalid-token",
            "X-Workspace-Id": str(db_workspace.id),
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chainlens_ingest_rejects_1024_embedding_dimension(
    client,
    db_workspace,
    monkeypatch,
    chainlens_headers,
):
    """Pattern 2: 1024-dim configured model fails fast."""
    from app.config import config

    class _FakeModel:
        dimension = 1024

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 1024 for _ in texts]

    monkeypatch.setattr(config, "embedding_model_instance", _FakeModel())

    payload = {
        "workspace_id": db_workspace.id,
        "scraper_id": "test.scraper",
        "run_id": "run-123",
        "chunks": [{"source_url": "https://x", "content": "c", "chunk_index": 0}],
    }
    resp = await client.post(
        "/v1/chainlens/ingest",
        json=payload,
        headers=chainlens_headers(db_workspace.id),
    )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_chainlens_ingest_records_job(
    client,
    db_session,
    db_workspace,
    fake_embedding_model_1536,
    chainlens_headers,
):
    """Pattern 6: chainlens_ingest_jobs row created with counts."""
    payload = {
        "workspace_id": db_workspace.id,
        "scraper_id": "test.scraper",
        "run_id": "run-123",
        "chunks": [
            {"source_url": "https://example.com/page", "content": "c", "chunk_index": 0}
        ],
    }
    resp = await client.post(
        "/v1/chainlens/ingest",
        json=payload,
        headers=chainlens_headers(db_workspace.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_received_count"] == 1
    assert body["chunks_ingested_count"] == 1

    job = (
        await db_session.execute(
            select(ChainLensIngestJob).where(
                ChainLensIngestJob.workspace_id == db_workspace.id,
                ChainLensIngestJob.scraper_id == "test.scraper",
                ChainLensIngestJob.run_id == "run-123",
            )
        )
    ).scalar_one_or_none()
    assert job is not None
    assert job.chunks_received_count == 1
    assert job.chunks_ingested_count == 1
