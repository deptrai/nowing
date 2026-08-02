"""Add extended statistics and drop the now-redundant single-column
research_thread_id index for the memories thread-recency read.

Story 3.14 (AC-3, evidence-driven, follow-up to migration 181):

Migration 181 added ``ix_memories_thread_recency`` (composite btree on
``research_thread_id, created_at, id``) to give the thread-recency query
(``WHERE workspace_id = :w AND research_thread_id = :t ORDER BY created_at
DESC, id DESC LIMIT 5``) an index path that satisfies the ORDER BY directly.
That index alone was not sufficient: a full-scale (200,400-row, two-cell)
rerun of ``scripts/benchmark_memory_story_3_14.py`` still failed the AC-3
ratio gate (10.18x observed vs <=3.0x required), because the planner
sometimes chose the *other* index (``ix_memories_research_thread_id``, plain
btree on ``research_thread_id`` alone) plus an explicit ``Sort`` node instead
of the new composite index.

Root cause, confirmed by a targeted two-workspace/two-thread repro
(``/tmp/repro4.py`` at production scale — 150,000 unscoped filler rows +
one 100-row thread + one 50,000-row thread): ``workspace_id`` and
``research_thread_id`` are functionally correlated in this table (every
thread-scoped memory belongs to exactly one workspace, so knowing the thread
almost fully determines the workspace), but PostgreSQL's default
single-column statistics assume every ``WHERE`` column is independent. For
the equality filter ``workspace_id = :w AND research_thread_id = :t``, the
planner therefore multiplies the two columns' independent selectivities and
drastically *underestimates* the combined row count — e.g. ``Plan Rows: 1``
for a predicate that actually matches 50,000 rows.

Adding ``CREATE STATISTICS ... (dependencies)`` alone measurably improved the
row estimate (a live 200,400-row artifact rerun went from a 10.18x total p95
growth ratio down to 6.35x — still over the <=3.0x gate) but did not fully
eliminate the flakiness: at production scale the corrected cardinality
estimate (``rows=1`` -> the true ~50,000) makes both candidate plans look
similarly expensive to the cost model, so the planner can still tip either
way depending on autovacuum/analyze timing and table bloat.

``MemoryHybridSearch.search()`` (``app/services/memory/search.py``) never
filters on ``Memory.research_thread_id`` without an accompanying
``workspace_id`` scope condition — ``research_thread_id`` is only ever
appended to ``base_conditions``, which always already contains exactly one
of ``workspace_id``/``user_id`` (see ``_scope_conditions``, D5). The
single-column ``ix_memories_research_thread_id`` index therefore has no
production query it uniquely serves: every equality filter on
``research_thread_id`` in this codebase is always paired with a
``workspace_id`` filter that the composite ``ix_memories_thread_recency``
index (whose leading column is ``research_thread_id``) already satisfies at
least as well, while also avoiding the explicit ``Sort`` node the
single-column index requires. Dropping the single-column index removes the
competing (worse) plan entirely, making the planner's choice deterministic
instead of cost-model-dependent — the standard fix once a redundant index is
confirmed to have no other consumer, rather than continuing to tune
statistics to bias a comparison that has no reason to be close.

Revision ID: 182
Revises: 181
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "182"
down_revision: str | None = "181"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATS_NAME = "memories_workspace_thread_dep"
OLD_INDEX_NAME = "ix_memories_research_thread_id"


def upgrade() -> None:
    op.execute(
        f"CREATE STATISTICS IF NOT EXISTS {STATS_NAME} (dependencies) "
        "ON workspace_id, research_thread_id FROM memories"
    )
    # Dropping the redundant single-column index is fast even on a warm table
    # and avoids the transactional restrictions of CONCURRENTLY, which is
    # problematic inside asyncpg/alembic autocommit blocks.
    op.execute(f"DROP INDEX IF EXISTS {OLD_INDEX_NAME}")
    op.execute("ANALYZE memories")


def downgrade() -> None:
    # CREATE INDEX on a hot table must be CONCURRENTLY and cannot run inside
    # a transaction.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {OLD_INDEX_NAME} "
            "ON memories (research_thread_id)"
        )
    op.execute(f"DROP STATISTICS IF EXISTS {STATS_NAME}")
