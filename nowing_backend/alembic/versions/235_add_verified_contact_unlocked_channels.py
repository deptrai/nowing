"""add per-channel unlock tracking to verified_contacts

Revision ID: 235
Revises: 232
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "235"
down_revision: str | None = "232"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    from sqlalchemy.engine import reflection

    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("verified_contacts", "unlocked_channels"):
        op.add_column(
            "verified_contacts",
            sa.Column(
                "unlocked_channels",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    if _column_exists("verified_contacts", "unlocked_channels"):
        op.drop_column("verified_contacts", "unlocked_channels")
