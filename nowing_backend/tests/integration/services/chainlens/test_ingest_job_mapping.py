"""Integration tests for chainlens ingest job mapping (Story 12-4e)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db import ChainLensIngestJob

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="red phase — pending AC-4/AC-5 integration")]


@pytest_asyncio.fixture
async def db_workspace(db_session):
    """Create a test workspace."""
    from app.db import User, Workspace

    user = User(
        id=uuid.uuid4(),
        email="test@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    workspace = Workspace(
        name="Test Space",
        user_id=user.id,
    )
    db_session.add(workspace)
    await db_session.flush()
    return workspace


@pytest.mark.asyncio
async def test_chain_lens_ingest_job_row_created_with_workspace_id_ingest_job_id_status(
    db_session, db_workspace, monkeypatch
):
    """ChainLensIngestJob row is created in Postgres with workspace_id, ingest_job_id, status."""
    import types

    import httpx
    import respx

    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService
    from app.services.scraper_chunks.schemas import Chunk, ChunkMetadata

    monkeypatch.setattr(
        ingest_mod,
        "config",
        types.SimpleNamespace(
            CHAINLENS_API_URL="https://chainlens.test",
            CHAINLENS_API_KEY="secret",
            CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
            CHAINLENS_INGEST_TIMEOUT_SECONDS=5,
            CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=3,
        ),
    )

    chunk = Chunk(
        content="Test job content",
        metadata=ChunkMetadata(
            source="nowing_scraper",
            sourceId="test:123",
            domain="vn_jobs",
            fetchedAt="2026-08-11T00:00:00+00:00",
            contentType="job",
            title="Data Engineer",
        ),
    )

    with respx.mock:
        route = respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(200, json={"ingestJobId": "job-test-123"})
        )
        service = NowingIngestService()
        result = await service.ingest(
            scraper_id="vn_jobs.aggregate",
            chunks=[chunk],
            workspace_id=db_workspace.id,
            session=db_session,
        )

    assert route.called
    assert result.ingest_job_id == "job-test-123"

    stmt = select(ChainLensIngestJob).where(
        ChainLensIngestJob.workspace_id == db_workspace.id
    )
    job_row = await db_session.execute(stmt)
    job = job_row.scalar_one_or_none()

    assert job is not None
    assert job.workspace_id == db_workspace.id
    assert job.scraper_id == "vn_jobs.aggregate"
    assert job.status == "ok"
    assert job.parent_ingest_job_id is not None or job.child_ingest_job_ids


@pytest.mark.asyncio
async def test_failed_batch_stores_dead_letter_payload(
    db_session, db_workspace, monkeypatch
):
    """Failed batch stores dead_letter_payload."""
    import types

    import httpx
    import respx

    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService
    from app.services.scraper_chunks.schemas import Chunk, ChunkMetadata

    monkeypatch.setattr(
        ingest_mod,
        "config",
        types.SimpleNamespace(
            CHAINLENS_API_URL="https://chainlens.test",
            CHAINLENS_API_KEY="secret",
            CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
            CHAINLENS_INGEST_TIMEOUT_SECONDS=5,
            CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=3,
        ),
    )

    chunk = Chunk(
        content="Test job content",
        metadata=ChunkMetadata(
            source="nowing_scraper",
            sourceId="test:123",
            domain="vn_jobs",
            fetchedAt="2026-08-11T00:00:00+00:00",
            contentType="job",
            title="Data Engineer",
        ),
    )

    with respx.mock:
        route = respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )
        service = NowingIngestService()
        result = await service.ingest(
            scraper_id="vn_jobs.aggregate",
            chunks=[chunk],
            workspace_id=db_workspace.id,
            session=db_session,
        )

    assert route.called
    assert result.status == "failed"

    stmt = select(ChainLensIngestJob).where(
        ChainLensIngestJob.workspace_id == db_workspace.id
    )
    job_row = await db_session.execute(stmt)
    job = job_row.scalar_one_or_none()

    assert job is not None
    assert job.dead_letter_payload is not None
    assert isinstance(job.dead_letter_payload, list)
    assert len(job.dead_letter_payload) > 0
