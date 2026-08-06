"""add source set tracking to canonical_merge_history

Revision ID: 194
Revises: 193
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.zero_publication import apply_publication

revision: str = "194"
down_revision: str | None = "193"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(stmt)


def upgrade() -> None:
    # ponytail: IF NOT EXISTS keeps this safe for databases that already
    # received these columns through an updated revision 193 in local dev.
    _exec_statements(
        "ALTER TABLE canonical_merge_history "
        "ADD COLUMN IF NOT EXISTS previous_source_ids JSONB NOT NULL DEFAULT '[]', "
        "ADD COLUMN IF NOT EXISTS new_source_ids JSONB NOT NULL DEFAULT '[]';",
    )
    # Reconcile zero_publication so canonical_entities gets the 13.2c shape
    # on databases that applied an older revision 193.
    apply_publication(op.get_bind())


def downgrade() -> None:
    _exec_statements(
        "ALTER TABLE canonical_merge_history "
        "DROP COLUMN IF EXISTS new_source_ids, "
        "DROP COLUMN IF EXISTS previous_source_ids;",
    )
    apply_publication(op.get_bind())
