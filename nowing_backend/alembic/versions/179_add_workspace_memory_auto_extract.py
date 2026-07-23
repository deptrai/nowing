"""Add workspace memory_auto_extract_enabled column.

Revision ID: 179
Revises: 178
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "179"
down_revision: str | None = "178"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "memory_auto_extract_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "memory_auto_extract_enabled")
