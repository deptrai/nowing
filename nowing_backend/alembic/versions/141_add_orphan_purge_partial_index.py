"""141_add_orphan_purge_partial_index — Story 11.7 T3: index for orphan purge

Revision ID: 141
Revises: 140

Adds a partial index optimised for the weekly orphan-purge query in
`cleanup_orphaned_crypto_snapshots` (Story 11.3). Without this index, on a
10M+ row `crypto_data_snapshots` table the orphan-detection query has to:

  1. Scan the existing `ix_crypto_snapshots_cache_lookup` index (which has
     `search_space_id` as leading column, so the `IS NOT NULL` filter helps)
  2. ...but `ORDER BY id ASC LIMIT 1000` can't use that index — id isn't in
     it. Postgres falls back to a sort over all matching rows.

This partial index covers exactly the orphan-candidate set ordered by `id`,
so the planner does a tight index-only scan + LIMIT.

EXPLAIN ANALYZE expectation (post-migration on production-shape data):
  -> Limit  (cost=0.42..XX rows=1000)
       -> Index Scan using ix_crypto_snapshots_orphan_purge on crypto_data_snapshots
          (with the NOT EXISTS subquery executed via Anti Join on searchspaces)

Acceptance target: each batch of 1000 deletes completes in < 60s on 10M rows.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "141"
down_revision: str | None = "140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Partial index: only the rows the orphan purge cares about, ordered by
    # `id ASC` so the LIMIT-1000 batch loop walks them in deterministic order
    # (matches the `ORDER BY id ASC` clause in `_async_cleanup_orphaned`).
    #
    # CONCURRENTLY: build without locking out the cleanup task / writer
    # workload. Cannot run inside a transaction — alembic is configured with
    # `transactional_ddl = False` for index migrations, OR we use raw SQL
    # outside the transaction.
    op.execute("COMMIT")  # close any open transaction Alembic started
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_crypto_snapshots_orphan_purge
        ON crypto_data_snapshots (id ASC)
        WHERE search_space_id IS NOT NULL
        """
    )
    op.execute("BEGIN")  # restore Alembic's expected transaction state


def downgrade() -> None:
    op.execute("COMMIT")
    op.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS ix_crypto_snapshots_orphan_purge"
    )
    op.execute("BEGIN")
