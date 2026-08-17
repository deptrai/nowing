"""Inbound stateless ChainLens -> Nowing chunk ingestion (Story 26.1 / AC-3)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import ChainLensChunk, ChainLensIngestJob

logger = logging.getLogger(__name__)


class ChainLensChunkItem(BaseModel):
    """One chunk from chainlens-research."""

    source_url: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    chunk_index: int = Field(default=0, ge=0)


class ChainLensIngestRequest(BaseModel):
    """Payload for ``POST /v1/chainlens/ingest``."""

    workspace_id: int = Field(..., gt=0)
    scraper_id: str = Field(..., min_length=1, max_length=100)
    run_id: str | None = Field(default=None, max_length=255)
    chunks: list[ChainLensChunkItem] = Field(default_factory=list)


class ChainLensIngestResponse(BaseModel):
    """Response for ``POST /v1/chainlens/ingest``."""

    status: str
    chunks_received_count: int
    chunks_ingested_count: int
    noop_source_ids: list[str] = Field(default_factory=list)


def _compute_chunk_id(
    workspace_id: int,
    source_url: str,
    chunk_index: int,
    content: str,
) -> UUID:
    """UUIDv5 chunk id scoped to workspace to prevent cross-tenant collisions."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    namespace_input = f"{workspace_id}:{source_url}:{chunk_index}:{digest}"
    return uuid5(NAMESPACE_URL, namespace_input)


class ChainLensIngestReceptionService:
    """Receive chunks from chainlens-research and persist them in Nowing Postgres."""

    async def ingest(
        self,
        session: AsyncSession,
        request: ChainLensIngestRequest,
    ) -> ChainLensIngestResponse:
        """Ingest chunks and return summary counts."""
        if not request.chunks:
            return ChainLensIngestResponse(
                status="noop",
                chunks_received_count=0,
                chunks_ingested_count=0,
                noop_source_ids=[],
            )

        # Fail fast if the configured embedding model does not produce 1536-dim vectors.
        embedding_model = config.embedding_model_instance
        if (
            embedding_model is None
            or getattr(embedding_model, "dimension", None) != 1536
        ):
            raise RuntimeError(
                "ChainLens chunk ingestion requires a 1536-dim embedding model"
            )

        contents = [chunk.content for chunk in request.chunks]
        embeddings = await embedding_model.embed_texts(contents)
        if len(embeddings) != len(contents):
            raise RuntimeError("embedding model returned fewer vectors than chunks")

        chunk_rows: list[dict[str, Any]] = []
        source_ids: set[str] = set()
        for chunk, vector in zip(request.chunks, embeddings, strict=True):
            if len(vector) != 1536:
                raise RuntimeError(
                    f"embedding dimension mismatch: expected 1536, got {len(vector)}"
                )
            chunk_id = _compute_chunk_id(
                request.workspace_id,
                chunk.source_url,
                chunk.chunk_index,
                chunk.content,
            )
            chunk_rows.append(
                {
                    "id": chunk_id,
                    "workspace_id": request.workspace_id,
                    "source_url": chunk.source_url,
                    "content": chunk.content,
                    "embedding": vector,
                    "chunk_index": chunk.chunk_index,
                }
            )
            source_ids.add(chunk.source_url)

        stmt = pg_insert(ChainLensChunk).values(chunk_rows)
        upsert = stmt.on_conflict_do_update(
            index_elements=["id", "workspace_id"],
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "chunk_index": stmt.excluded.chunk_index,
            },
        )

        result = await session.execute(upsert.returning(ChainLensChunk.id))
        inserted_ids = {row.id for row in result.all()}

        ingested_source_ids = {
            chunk.source_url
            for chunk, row in zip(request.chunks, chunk_rows, strict=True)
            if row["id"] in inserted_ids
        }
        noop_source_ids = sorted(source_ids - ingested_source_ids)

        # Record the chainlens ingest job for observability.
        job = ChainLensIngestJob(
            workspace_id=request.workspace_id,
            scraper_id=request.scraper_id,
            run_id=request.run_id,
            status="completed" if len(inserted_ids) > 0 else "noop",
            ingested_source_ids=sorted(ingested_source_ids),
            noop_source_ids=noop_source_ids,
            chunks_received_count=len(request.chunks),
            chunks_ingested_count=len(inserted_ids),
        )
        session.add(job)

        return ChainLensIngestResponse(
            status="completed" if len(inserted_ids) > 0 else "noop",
            chunks_received_count=len(request.chunks),
            chunks_ingested_count=len(inserted_ids),
            noop_source_ids=noop_source_ids,
        )
