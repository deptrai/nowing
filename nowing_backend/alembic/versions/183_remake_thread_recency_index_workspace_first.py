"""Remake the thread-recency index with workspace_id as the leading column.

Story 3.14 (AC-3, evidence follow-up to migrations 181 and 182):

Migration 181 added ``ix_memories_thread_recency`` as
``(research_thread_id, created_at, id)`` and migration 182 added
functional-dependency statistics and dropped the redundant single-column
index. A full-scale benchmark rerun still failed the AC-3 total p95 growth
ratio gate for ``thread-recency`` (3.6x at 100 vs 50,000 rows, > 3.0x).

The captured EXPLAIN shows the planner using the composite index with
``Index Cond: research_thread_id = :t`` and then applying a
``Filter: workspace_id = :w`` over the entire thread's rows. Because the
current index has no ``workspace_id`` column, it cannot prune at the index
level; recency is effectively O(thread size) instead of O(log n).

``MemoryHybridSearch.search()`` always filters on exactly one scope
(``workspace_id`` or ``user_id``) and only adds ``research_thread_id`` to
that scope. The thread-recency query is therefore always
``WHERE workspace_id = :w AND research_thread_id = :t``. A composite
btree on ``(workspace_id, research_thread_id, created_at, id)`` (still
partial ``WHERE research_thread_id IS NOT NULL``) lets the planner perform
both equality lookups at the index level and walk the leading ordered
columns in reverse to satisfy ``ORDER BY created_at DESC, id DESC LIMIT 5``
without a post-filter scan.

Revision ID: 183
Revises: 182
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "183"
down_revision: str | None = "182"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_memories_thread_recency"


def upgrade() -> None:
    # DROP INDEX is a quick catalog update; the brief ACCESS EXCLUSIVE lock
    # is acceptable. CREATE INDEX must be CONCURRENTLY so the build on a hot
    # table does not block writes for the full duration.
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON memories (workspace_id, research_thread_id, created_at, id) "
            "WHERE research_thread_id IS NOT NULL"
        )
    op.execute("ANALYZE memories")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON memories (research_thread_id, created_at, id) "
            "WHERE research_thread_id IS NOT NULL"
        )
    op.execute("ANALYZE memories")
