"""Add workspace vertical column.

Revision ID: 192
Revises: 191
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "192"
down_revision: str | None = "191"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "vertical",
            sa.String(64),
            nullable=False,
            server_default="general",
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "vertical")
