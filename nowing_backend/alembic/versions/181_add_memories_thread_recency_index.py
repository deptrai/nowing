"""Add composite index for thread-scoped memory recency reads.

Story 3.14 (AC-3, evidence-driven):

The recency branch of ``MemoryHybridSearch.search`` runs
``WHERE workspace_id = :w AND research_thread_id = :t
ORDER BY created_at DESC, id DESC LIMIT 5``. With only the single-column
``ix_memories_research_thread_id`` index, PostgreSQL index-scans every row of
the thread and top-N sorts them — O(thread size). The Story 3.14 benchmark
(``scripts/benchmark_memory_story_3_14.py``) measured total p95 growing from
3.33ms at 100 rows to 30.12ms at 50,000 rows (ratio 9.05, gate <= 3.0), with
the captured EXPLAIN showing Index Scan -> Sort -> Limit.

A composite btree on ``(workspace_id, research_thread_id, created_at, id)``
lets the planner satisfy the ORDER BY via a backward index scan under the
leading-column equalities and stop at LIMIT 5 — O(log n). Partial
(``research_thread_id IS NOT NULL``) because the recency query always binds a
concrete thread id and most memories are not thread-scoped. ``workspace_id``
leads because every recency filter is scoped to a workspace before a thread
is appended (see ``_scope_conditions`` in ``app/services/memory/search.py``).

Revision ID: 181
Revises: 180
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "181"
down_revision: str | None = "180"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_memories_thread_recency"


def upgrade() -> None:
    # CREATE INDEX on a hot table must be CONCURRENTLY and cannot run inside
    # a transaction. Use an autocommit block and raw SQL for the partial index.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON memories (workspace_id, research_thread_id, created_at, id) "
            "WHERE research_thread_id IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
