"""Red-phase ATDD unit tests for Story 26.1 ChainLens -> Nowing chunk ingestion.

Tests focus on AC-3: stateless chunk ingestion, UUIDv5 id, 1536-dim embedding,
chainlens_ingest_jobs tracking.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

import app.services.chainlens.ingest_reception as ingest_reception
from app.db import Workspace, get_async_session

pytestmark = pytest.mark.unit


class _FakeEmbeddingModel:
    """Hermetic fake embedding model returning 1536-dim vectors."""

    dimension = 1536

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]

    async def embed_text(self, text: str) -> list[float]:
        return [0.0] * self.dimension


class _FakeResult:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any, _params: Any | None = None) -> _FakeResult:
        return _FakeResult(self._rows)

    async def get(self, model: type, ident: Any) -> Any | None:
        if model is Workspace:
            return SimpleNamespace(id=ident)
        return None

    async def commit(self) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def refresh(self, _obj: Any) -> None:
        pass


class _NoAuth:
    """Simulates an invalid/missing ChainLens service token."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def validate_inbound_token(self, _request: Any) -> Any:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


@pytest.fixture
def chainlens_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Test client for the chainlens-internal router with failing auth."""
    from app.routes import chainlens_internal as internal_mod

    monkeypatch.setattr(internal_mod, "ChainLensServiceAuth", _NoAuth)

    async def _fake_session():
        yield _FakeSession()

    app = FastAPI()
    app.include_router(internal_mod.router, prefix="/v1")
    app.dependency_overrides[get_async_session] = _fake_session
    return TestClient(app)


class TestChainLensIngestReception:
    """AC-3: POST /v1/chainlens/ingest"""

    def test_chunk_id_includes_workspace_id(self) -> None:
        """should compute UUIDv5 with workspace_id in the input string."""
        workspace_id = 42
        source_url = "https://example.com/page"
        idx = 0
        content = "test content"
        expected = uuid5(
            NAMESPACE_URL,
            f"{workspace_id}:{source_url}:{idx}:{hashlib.sha256(content.encode()).hexdigest()}",
        )
        result = ingest_reception._compute_chunk_id(
            workspace_id, source_url, idx, content
        )
        assert result == expected

    def test_chunk_id_same_url_different_workspace_is_different(self) -> None:
        """should generate different UUID for same URL/content across two workspaces."""
        source_url = "https://example.com/page"
        content = "same content"
        id1 = ingest_reception._compute_chunk_id(1, source_url, 0, content)
        id2 = ingest_reception._compute_chunk_id(2, source_url, 0, content)
        assert id1 != id2

    def test_ingest_rejects_invalid_token(self, chainlens_client: TestClient) -> None:
        """should return 401 when ChainLensServiceAuth validation fails."""
        response = chainlens_client.post(
            "/v1/chainlens/ingest",
            headers={
                "Authorization": "Bearer bad-token",
                "X-Workspace-Id": "42",
            },
            json={
                "workspace_id": 42,
                "scraper_id": "test",
                "chunks": [
                    {"source_url": "https://example.com", "content": "x"}
                ],
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ingest_fails_fast_on_wrong_embedding_dimension(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should fail fast when config.embedding_model_instance.dimension != 1536."""
        from app.config import config

        fake = _FakeEmbeddingModel()
        fake.dimension = 1024
        monkeypatch.setattr(config, "embedding_model_instance", fake)

        service = ingest_reception.ChainLensIngestReceptionService()
        request = ingest_reception.ChainLensIngestRequest(
            workspace_id=1,
            scraper_id="test",
            chunks=[
                ingest_reception.ChainLensChunkItem(
                    source_url="https://example.com", content="x"
                )
            ],
        )

        with pytest.raises(RuntimeError, match="1536"):
            await service.ingest(_FakeSession(), request=request)

    @pytest.mark.asyncio
    async def test_ingest_records_chainlens_ingest_job(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should create/update chainlens_ingest_jobs with status and counts."""
        from app.config import config

        monkeypatch.setattr(config, "embedding_model_instance", _FakeEmbeddingModel())

        chunk1 = ingest_reception.ChainLensChunkItem(
            source_url="https://a.com", content="content a"
        )
        chunk2 = ingest_reception.ChainLensChunkItem(
            source_url="https://b.com", content="content b"
        )
        request = ingest_reception.ChainLensIngestRequest(
            workspace_id=1, scraper_id="s", chunks=[chunk1, chunk2]
        )

        id1 = ingest_reception._compute_chunk_id(
            request.workspace_id, chunk1.source_url, chunk1.chunk_index, chunk1.content
        )
        id2 = ingest_reception._compute_chunk_id(
            request.workspace_id, chunk2.source_url, chunk2.chunk_index, chunk2.content
        )

        session = _FakeSession(rows=[SimpleNamespace(id=id1), SimpleNamespace(id=id2)])
        service = ingest_reception.ChainLensIngestReceptionService()
        response = await service.ingest(session, request=request)

        assert response.status == "completed"
        assert response.chunks_received_count == 2
        assert response.chunks_ingested_count == 2
        assert response.noop_source_ids == []

        assert len(session.added) == 1
        job = session.added[0]
        assert type(job).__name__ == "ChainLensIngestJob"
        assert job.status == "completed"
        assert job.scraper_id == "s"
        assert job.workspace_id == 1
        assert job.chunks_received_count == 2
        assert job.chunks_ingested_count == 2
        assert set(job.ingested_source_ids) == {chunk1.source_url, chunk2.source_url}
        assert job.noop_source_ids == []

    @pytest.mark.asyncio
    async def test_ingest_on_conflict_do_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should report noop_source_ids for chunks that were not inserted."""
        from app.config import config

        monkeypatch.setattr(config, "embedding_model_instance", _FakeEmbeddingModel())

        chunk1 = ingest_reception.ChainLensChunkItem(
            source_url="https://a.com", content="content a"
        )
        chunk2 = ingest_reception.ChainLensChunkItem(
            source_url="https://b.com", content="content b"
        )
        request = ingest_reception.ChainLensIngestRequest(
            workspace_id=1, scraper_id="s", chunks=[chunk1, chunk2]
        )

        id1 = ingest_reception._compute_chunk_id(
            request.workspace_id, chunk1.source_url, chunk1.chunk_index, chunk1.content
        )

        # Simulate a conflict: the database returns only the first id.
        session = _FakeSession(rows=[SimpleNamespace(id=id1)])
        service = ingest_reception.ChainLensIngestReceptionService()
        response = await service.ingest(session, request=request)

        assert response.status == "completed"
        assert response.chunks_received_count == 2
        assert response.chunks_ingested_count == 1
        assert response.noop_source_ids == [chunk2.source_url]

        job = session.added[0]
        assert job.chunks_ingested_count == 1
        assert job.noop_source_ids == [chunk2.source_url]
