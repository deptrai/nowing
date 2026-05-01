"""139_add_workspace_id_to_crypto_cache — Adversarial Review Fix: Workspace Isolation

Revision ID: 139
Revises: 138

Adds search_space_id to crypto_data_snapshots to enforce workspace isolation (RLS).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "139"
down_revision: str | None = "138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add search_space_id column (nullable=True initially to allow migration)
    op.add_column(
        "crypto_data_snapshots",
        sa.Column("search_space_id", sa.Integer(), nullable=True)
    )

    # 2. Add foreign key constraint
    op.create_foreign_key(
        "fk_crypto_snapshots_search_space_id",
        "crypto_data_snapshots",
        "searchspaces",
        ["search_space_id"],
        ["id"],
        ondelete="CASCADE"
    )

    # 3. Create index for performance
    op.create_index(
        "ix_crypto_snapshots_search_space_id",
        "crypto_data_snapshots",
        ["search_space_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_crypto_snapshots_search_space_id", table_name="crypto_data_snapshots")
    op.drop_constraint("fk_crypto_snapshots_search_space_id", "crypto_data_snapshots", type_="foreignkey")
    op.drop_column("crypto_data_snapshots", "search_space_id")
