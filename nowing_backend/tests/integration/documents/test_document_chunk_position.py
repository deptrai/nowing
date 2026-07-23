"""Red-phase ATDD tests for Story 3.6: Citation Scroll-to-Highlight.

Verifies that `/documents/by-chunk/{chunk_id}` exposes `Chunk.position` in API responses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import (
    Chunk,
    Document,
    DocumentType,
    User,
    Workspace,
)

EMBEDDING_DIM = app_config.embedding_model_instance.dimension
DUMMY_EMBEDDING = [0.1] * EMBEDDING_DIM

pytestmark = [
    pytest.mark.integration,
]


def _make_document(
    *,
    title: str,
    content: str,
    workspace_id: int,
    created_by_id: str,
) -> Document:
    return Document(
        title=title,
        document_type=DocumentType.NOTE,
        content=content,
        content_hash=uuid.uuid4().hex,
        unique_identifier_hash=uuid.uuid4().hex,
        source_markdown=content,
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        updated_at=datetime.now(UTC),
        document_metadata={},
        status={"state": "ready"},
    )


def _make_chunk(*, content: str, document_id: int, position: int) -> Chunk:
    return Chunk(
        content=content,
        document_id=document_id,
        position=position,
        embedding=DUMMY_EMBEDDING,
    )


@pytest_asyncio.fixture
async def seeded_document(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> Document:
    """Create a document with three ordered chunks and refresh the ORM relationship."""
    user_id = str(db_user.id)
    content = "# Apple\n\nBanana section.\n\nCherry conclusion."
    doc = _make_document(
        title="ATDD Citation Scroll Doc",
        content=content,
        workspace_id=db_workspace.id,
        created_by_id=user_id,
    )
    db_session.add(doc)
    await db_session.flush()

    chunks = [
        _make_chunk(
            content="# Apple",
            document_id=doc.id,
            position=0,
        ),
        _make_chunk(
            content="Banana section.",
            document_id=doc.id,
            position=1,
        ),
        _make_chunk(
            content="Cherry conclusion.",
            document_id=doc.id,
            position=2,
        ),
    ]
    db_session.add_all(chunks)
    await db_session.flush()
    await db_session.refresh(doc, attribute_names=["chunks"])
    return doc


class TestGetDocumentByChunkExposesPosition:
    """AC 2 — /documents/by-chunk/{chunk_id} must include chunk position."""

    async def test_cited_chunk_has_position(
        self,
        client: AsyncClient,
        seeded_document: Document,
    ) -> None:
        """The chunk that matches the requested chunk_id must expose its absolute position."""
        middle_chunk = seeded_document.chunks[1]
        response = await client.get(f"/api/v1/documents/by-chunk/{middle_chunk.id}?chunk_window=1")
        assert response.status_code == 200
        payload = response.json()
        assert "chunks" in payload
        for chunk in payload["chunks"]:
            assert "position" in chunk, "ChunkRead must expose position"
            assert isinstance(chunk["position"], int)

    async def test_chunk_positions_increase_with_order(
        self,
        client: AsyncClient,
        seeded_document: Document,
    ) -> None:
        """Returned chunks in a window must be ordered by ascending position."""
        middle_chunk = seeded_document.chunks[1]
        response = await client.get(f"/api/v1/documents/by-chunk/{middle_chunk.id}?chunk_window=5")
        assert response.status_code == 200
        payload = response.json()
        positions = [chunk["position"] for chunk in payload["chunks"]]
        assert positions == sorted(positions)
