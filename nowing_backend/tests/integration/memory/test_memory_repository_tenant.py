"""Tenant-scoped behavior in MemoryRepository (defer items from Story 3.13 / 18.6)."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import (
    Memory,
    MemoryRelationType,
    MemorySourceType,
    MemoryType,
    User,
    Workspace,
)
from app.services.memory.repository import MemoryRepository

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension


def _similar_embedding() -> list[float]:
    # Non-zero vector: pgvector cosine distance is well-defined and 0 for
    # identical vectors, so duplicate detection matches within the threshold.
    return [0.1] * _EMBEDDING_DIM


async def _make_memory(
    session: AsyncSession,
    workspace: Workspace,
    content: str,
    *,
    client_id: str | None = None,
    created_by: User | None = None,
) -> Memory:
    """Insert a memory row directly so dedup logic does not collapse variants."""
    memory = Memory(
        workspace_id=workspace.id,
        content=content,
        embedding=_similar_embedding(),
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        client_id=client_id,
        created_by_id=created_by.id if created_by else None,
    )
    session.add(memory)
    await session.flush()
    return memory


async def test_find_near_duplicate_scopes_by_client_id(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """Deduplication must not match a memory from another client scope."""
    repo = MemoryRepository(session=db_session)

    internal = await _make_memory(
        db_session, db_workspace, "shared fact", client_id=None, created_by=db_user
    )
    acme = await _make_memory(
        db_session, db_workspace, "shared fact", client_id="acme", created_by=db_user
    )

    embedding = np.array(_similar_embedding())

    found_internal = await repo._find_near_duplicate(
        db_workspace.id,
        "shared fact",
        embedding,
        client_id=None,
    )
    assert found_internal is not None
    assert found_internal.id == internal.id

    found_acme = await repo._find_near_duplicate(
        db_workspace.id,
        "shared fact",
        embedding,
        client_id="acme",
    )
    assert found_acme is not None
    assert found_acme.id == acme.id

    found_other = await repo._find_near_duplicate(
        db_workspace.id,
        "shared fact",
        embedding,
        client_id="other",
    )
    assert found_other is None


async def test_add_relation_inherits_client_id(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """A relation carries the source memory's client_id and stays tenant-scoped."""
    repo = MemoryRepository(session=db_session)

    source = await _make_memory(
        db_session, db_workspace, "source", client_id="acme", created_by=db_user
    )
    target = await _make_memory(
        db_session, db_workspace, "target", client_id="acme", created_by=db_user
    )

    relation = await repo.add_relation(
        workspace_id=db_workspace.id,
        from_memory_id=source.id,
        to_memory_id=target.id,
        relation_type=MemoryRelationType.RELATED,
    )

    assert relation.workspace_id == db_workspace.id
    assert relation.client_id == "acme"
    assert relation.from_memory_id == source.id
    assert relation.to_memory_id == target.id


async def test_add_relation_rejects_cross_client_target(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """Relating an acme memory to an internal memory must fail."""
    repo = MemoryRepository(session=db_session)

    source = await _make_memory(
        db_session, db_workspace, "source", client_id="acme", created_by=db_user
    )
    target = await _make_memory(
        db_session, db_workspace, "target", client_id=None, created_by=db_user
    )

    with pytest.raises(ValueError, match="different client scope"):
        await repo.add_relation(
            workspace_id=db_workspace.id,
            from_memory_id=source.id,
            to_memory_id=target.id,
            relation_type=MemoryRelationType.RELATED,
        )


async def test_add_relation_rejects_cross_workspace_source(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """A relation whose workspace does not match the source memory must fail."""
    other_workspace = Workspace(name="Other", user_id=db_user.id)
    db_session.add(other_workspace)
    await db_session.flush()

    source = await _make_memory(
        db_session, other_workspace, "source", client_id=None, created_by=db_user
    )

    repo = MemoryRepository(session=db_session)
    with pytest.raises(ValueError, match="does not belong to workspace"):
        await repo.add_relation(
            workspace_id=db_workspace.id,
            from_memory_id=source.id,
            to_memory_id=None,
            relation_type=MemoryRelationType.RELATED,
        )
