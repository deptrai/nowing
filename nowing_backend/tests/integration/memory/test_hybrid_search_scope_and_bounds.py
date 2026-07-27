"""Real-DB tests for ``MemoryHybridSearch`` scope/bounds/scoring (Story 3.14, D5/D6).

Embeddings are supplied directly (not via the real embedding model) so
ranking is deterministic and under test control. These exercise the shared
search path directly against Postgres+pgvector — RRF/HNSW/GIN behavior and
the D6 bounded-candidate/validation contract cannot be meaningfully faked
with mocks.
"""

from __future__ import annotations

import pytest

from app.db import Memory, MemorySourceType, MemoryType
from app.services.memory.search import MemoryHybridSearch

pytestmark = [pytest.mark.integration, pytest.mark.memory]


async def _add_memory(db_session, *, workspace_id=None, created_by_id=None, content, embedding):
    memory = Memory(
        workspace_id=workspace_id,
        content=content,
        embedding=embedding,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_by_id=created_by_id,
    )
    db_session.add(memory)
    await db_session.flush()
    return memory


async def test_search_personal_scope_isolated_by_user(db_session, db_user, db_other_user):
    """Personal scope (user_id) never leaks another user's workspace-less memory."""
    mine = await _add_memory(
        db_session,
        created_by_id=db_user.id,
        content="Alpha quarterly personal note",
        embedding=[0.2] * 384,
    )
    await _add_memory(
        db_session,
        created_by_id=db_other_user.id,
        content="Alpha quarterly personal note from someone else",
        embedding=[0.2] * 384,
    )

    hits = await MemoryHybridSearch(db_session).search(
        user_id=db_user.id,
        query="alpha quarterly",
        query_embedding=[0.2] * 384,
        top_k=5,
    )

    ids = [hit.memory.id for hit in hits]
    assert mine.id in ids
    assert all(hit.memory.created_by_id == db_user.id for hit in hits)


async def test_search_bounds_output_to_five_regardless_of_top_k(db_session, db_workspace):
    """D6: output is bounded to 5 even when top_k is requested much larger."""
    for i in range(8):
        await _add_memory(
            db_session,
            workspace_id=db_workspace.id,
            content=f"Widget report number {i}",
            embedding=[0.1 + i * 0.01] * 384,
        )

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="widget report",
        query_embedding=[0.1] * 384,
        top_k=100,
    )

    assert len(hits) <= 5


async def test_search_ranked_hits_have_finite_score_and_similarity(db_session, db_workspace):
    """D6: similarity is computed for every ranked hit — never null/fake for a ranked query."""
    for i in range(3):
        await _add_memory(
            db_session,
            workspace_id=db_workspace.id,
            content=f"Gadget launch plan {i}",
            embedding=[0.3 + i * 0.01] * 384,
        )

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="gadget launch",
        query_embedding=[0.3] * 384,
        top_k=5,
    )

    assert hits
    for hit in hits:
        assert hit.score is not None and hit.score == hit.score  # not NaN
        assert hit.similarity is not None and hit.similarity == hit.similarity


async def test_search_skips_stored_zero_norm_embedding(db_session, db_workspace):
    """D6: a legacy invalid stored row (zero norm) is audited/dropped, not raised."""
    valid = await _add_memory(
        db_session,
        workspace_id=db_workspace.id,
        content="Sprocket rollout status valid",
        embedding=[0.4] * 384,
    )
    invalid = await _add_memory(
        db_session,
        workspace_id=db_workspace.id,
        content="Sprocket rollout status invalid",
        embedding=[0.0] * 384,
    )

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="sprocket rollout",
        query_embedding=[0.4] * 384,
        top_k=5,
    )

    ids = [hit.memory.id for hit in hits]
    assert valid.id in ids
    assert invalid.id not in ids


async def test_search_recency_mode_returns_null_score_and_similarity(db_session, db_workspace):
    """Query-less (recency) recall never fakes a 0.0 score/similarity — both are null."""
    for i in range(3):
        await _add_memory(
            db_session,
            workspace_id=db_workspace.id,
            content=f"Recency note {i}",
            embedding=[0.5] * 384,
        )

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="",
        query_embedding=None,
        top_k=5,
    )

    assert hits
    assert all(hit.score is None and hit.similarity is None for hit in hits)


async def test_search_missing_scope_raises_value_error(db_session):
    """D5: neither workspace_id nor user_id supplied raises before SQL."""
    with pytest.raises(ValueError):
        await MemoryHybridSearch(db_session).search(query="anything", query_embedding=None)
