"""drop canonical entity tables (Epic 13 removed)

Revision ID: d33c362fa627
Revises: f984b591d763
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d33c362fa627"
down_revision: str | None = "f984b591d763"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop Epic 13 canonical entity tables; chainlens-research owns the index."""
    op.execute("DROP TABLE IF EXISTS canonical_persist_outbox CASCADE;")
    op.execute("DROP TABLE IF EXISTS canonical_merge_history CASCADE;")
    op.execute("DROP TABLE IF EXISTS canonical_entity_sources CASCADE;")
    op.execute("DROP TABLE IF EXISTS canonical_entities CASCADE;")

    # Remove stale zero-publication references for tables that no longer exist.
    op.execute(
        "DELETE FROM zero_publication WHERE table_name IN "
        "('canonical_entities', 'canonical_entity_sources', "
        "'canonical_merge_history', 'canonical_persist_outbox');"
    )


def downgrade() -> None:
    """Canonical tables are not recreated; they belong to chainlens-research."""
    raise NotImplementedError(
        "Cannot downgrade: canonical entity tables were intentionally removed."
    )
