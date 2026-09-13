"""Real-DB tests for ``MemoryHybridSearch`` scope/bounds/scoring (Story 3.14, D5/D6).

Embeddings are supplied directly (not via the real embedding model) so
ranking is deterministic and under test control. These exercise the shared
search path directly against Postgres+pgvector — RRF/HNSW/GIN behavior and
the D6 bounded-candidate/validation contract cannot be meaningfully faked
with mocks.
"""

from __future__ import annotations

import pytest

from app.config import config
from app.db import Memory, MemorySourceType, MemoryType, ResearchThread
from app.services.memory.search import MemoryHybridSearch

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_EMBEDDING_DIM = config.embedding_model_instance.dimension


async def _add_memory(
    db_session,
    *,
    workspace_id=None,
    created_by_id=None,
    research_thread_id=None,
    content,
    embedding,
):
    memory = Memory(
        workspace_id=workspace_id,
        research_thread_id=research_thread_id,
        content=content,
        embedding=embedding,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_by_id=created_by_id,
    )
    db_session.add(memory)
    await db_session.flush()
    return memory


async def test_search_personal_scope_isolated_by_user(
    db_session, db_user, db_other_user
):
    """Personal scope (user_id) never leaks another user's workspace-less memory."""
    mine = await _add_memory(
        db_session,
        created_by_id=db_user.id,
        content="Alpha quarterly personal note",
        embedding=[0.2] * _EMBEDDING_DIM,
    )
    await _add_memory(
        db_session,
        created_by_id=db_other_user.id,
        content="Alpha quarterly personal note from someone else",
        embedding=[0.2] * _EMBEDDING_DIM,
    )

    hits = await MemoryHybridSearch(db_session).search(
        user_id=db_user.id,
        query="alpha quarterly",
        query_embedding=[0.2] * _EMBEDDING_DIM,
        top_k=5,
    )

    ids = [hit.memory.id for hit in hits]
    assert mine.id in ids
    assert all(hit.memory.created_by_id == db_user.id for hit in hits)


async def test_search_rejects_top_k_out_of_bounds(db_session, db_workspace):
    """D9: internal search raises for 0, bool, or top_k above the 5 ceiling."""
    for i in range(8):
        await _add_memory(
            db_session,
            workspace_id=db_workspace.id,
            content=f"Widget report number {i}",
            embedding=[0.1 + i * 0.01] * _EMBEDDING_DIM,
        )

    with pytest.raises(ValueError):
        await MemoryHybridSearch(db_session).search(
            workspace_id=db_workspace.id,
            query="widget report",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            top_k=100,
        )


async def test_search_ranked_hits_have_finite_score_and_similarity(
    db_session, db_workspace
):
    """D6: similarity is computed for every ranked hit — never null/fake for a ranked query."""
    for i in range(3):
        await _add_memory(
            db_session,
            workspace_id=db_workspace.id,
            content=f"Gadget launch plan {i}",
            embedding=[0.3 + i * 0.001] * _EMBEDDING_DIM,
        )

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="gadget launch",
        query_embedding=[0.3] * _EMBEDDING_DIM,
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
        embedding=[0.4] * _EMBEDDING_DIM,
    )
    invalid = await _add_memory(
        db_session,
        workspace_id=db_workspace.id,
        content="Sprocket rollout status invalid",
        embedding=[0.0] * _EMBEDDING_DIM,
    )

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="sprocket rollout",
        query_embedding=[0.4] * _EMBEDDING_DIM,
        top_k=5,
    )

    ids = [hit.memory.id for hit in hits]
    assert valid.id in ids
    assert invalid.id not in ids


async def test_search_recency_mode_returns_null_score_and_similarity(
    db_session, db_workspace, db_user
):
    """Query-less (recency) recall never fakes a 0.0 score/similarity — both are null."""
    thread = ResearchThread(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        title="Recency thread",
    )
    db_session.add(thread)
    await db_session.flush()

    for i in range(3):
        await _add_memory(
            db_session,
            workspace_id=db_workspace.id,
            research_thread_id=thread.id,
            content=f"Recency note {i}",
            embedding=[0.5] * _EMBEDDING_DIM,
        )

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="",
        query_embedding=None,
        research_thread_id=thread.id,
        top_k=5,
    )

    assert hits
    assert all(hit.score is None and hit.similarity is None for hit in hits)


async def test_search_missing_scope_raises_value_error(db_session):
    """D5: neither workspace_id nor user_id supplied raises before SQL."""
    with pytest.raises(ValueError):
        await MemoryHybridSearch(db_session).search(
            query="anything", query_embedding=None
        )


async def test_rrf_tie_break_by_similarity(db_session, db_workspace):
    """RRF tie-break: when two hits have identical RRF score, higher similarity wins.

    Memory A: semantic rank 1 (closer), keyword rank 2 (intervening words -> lower ts_rank_cd)
    Memory B: semantic rank 2 (farther), keyword rank 1 (multiple covers -> higher ts_rank_cd)
    RRF scores are identical: 1/(60+1) + 1/(60+2) == 1/(60+2) + 1/(60+1).
    Memory A must win because similarity DESC precedes created_at and id.
    """
    from datetime import datetime, timezone

    t0 = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    half = _EMBEDDING_DIM // 2
    query_emb = [1.0] * half + [0.0] * (_EMBEDDING_DIM - half)
    closer_emb = [1.0] * half + [0.0] * (_EMBEDDING_DIM - half)  # angle 0, distance 0
    farther_emb = [0.5] * half + [0.5] * (_EMBEDDING_DIM - half)  # angle > 0, distance > 0

    mem_a = Memory(
        workspace_id=db_workspace.id,
        content="alpha intervening words here beta",
        embedding=closer_emb,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_at=t0,
    )
    mem_b = Memory(
        workspace_id=db_workspace.id,
        content="alpha beta and again alpha beta and third alpha beta",
        embedding=farther_emb,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_at=t0,
    )
    db_session.add_all([mem_a, mem_b])
    await db_session.flush()

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="alpha beta",
        query_embedding=query_emb,
        top_k=5,
    )

    ids = [hit.memory.id for hit in hits[:2]]
    assert len(ids) == 2
    assert pytest.approx(hits[0].score, rel=1e-6) == hits[1].score
    assert hits[0].similarity > hits[1].similarity
    assert ids[0] == mem_a.id
    assert ids[1] == mem_b.id


async def test_rrf_tie_break_by_created_at(db_session, db_workspace):
    """RRF tie-break: when RRF score AND similarity are identical, newer created_at wins.

    mem_a: semantic rank 1 (same embedding, smaller id), keyword rank 2 (lower ts_rank_cd)
    mem_b: semantic rank 2 (same embedding, larger id), keyword rank 1 (higher ts_rank_cd)
    RRF scores: 1/61 + 1/62 == 1/62 + 1/61.
    Similarities: identical because same embedding vector.
    mem_b is newer (created_at + 2 days), so mem_b must win on created_at DESC.
    """
    from datetime import datetime, timedelta, timezone

    t_old = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    t_new = t_old + timedelta(days=2)
    same_emb = [0.25] * _EMBEDDING_DIM

    mem_a = Memory(
        workspace_id=db_workspace.id,
        content="alpha intervening words here beta",
        embedding=same_emb,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_at=t_old,
    )
    db_session.add(mem_a)
    await db_session.flush()

    mem_b = Memory(
        workspace_id=db_workspace.id,
        content="alpha beta and again alpha beta and third alpha beta",
        embedding=same_emb,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_at=t_new,
    )
    db_session.add(mem_b)
    await db_session.flush()

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="alpha beta",
        query_embedding=same_emb,
        top_k=5,
    )

    ids = [hit.memory.id for hit in hits[:2]]
    assert len(ids) == 2
    assert pytest.approx(hits[0].score, rel=1e-6) == hits[1].score
    assert pytest.approx(hits[0].similarity, rel=1e-6) == hits[1].similarity
    assert hits[0].memory.created_at > hits[1].memory.created_at
    assert ids[0] == mem_b.id
    assert ids[1] == mem_a.id


async def test_rrf_tie_break_by_id(db_session, db_workspace):
    """RRF tie-break: when score, similarity, and created_at are identical, smaller id wins.

    mem_a: semantic rank 1 (same embedding, smaller id), keyword rank 2 (lower ts_rank_cd)
    mem_b: semantic rank 2 (same embedding, larger id), keyword rank 1 (higher ts_rank_cd)
    Both have same created_at and same embedding -> score, similarity, and created_at are identical!
    mem_a.id < mem_b.id -> mem_a must win on id ASC.
    """
    from datetime import datetime, timezone

    t_same = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    same_emb = [0.35] * _EMBEDDING_DIM

    mem_a = Memory(
        workspace_id=db_workspace.id,
        content="alpha intervening words here beta",
        embedding=same_emb,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_at=t_same,
    )
    db_session.add(mem_a)
    await db_session.flush()

    mem_b = Memory(
        workspace_id=db_workspace.id,
        content="alpha beta and again alpha beta and third alpha beta",
        embedding=same_emb,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        created_at=t_same,
    )
    db_session.add(mem_b)
    await db_session.flush()

    assert mem_a.id < mem_b.id

    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="alpha beta",
        query_embedding=same_emb,
        top_k=5,
    )

    ids = [hit.memory.id for hit in hits[:2]]
    assert len(ids) == 2
    assert pytest.approx(hits[0].score, rel=1e-6) == hits[1].score
    assert pytest.approx(hits[0].similarity, rel=1e-6) == hits[1].similarity
    assert hits[0].memory.created_at == hits[1].memory.created_at
    assert ids[0] == mem_a.id
    assert ids[1] == mem_b.id

