"""add memory retention and storage cap

Revision ID: 234_add_memory_retention
Revises: c7a42e189d20
Create Date: 2026-08-27 02:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "234_add_memory_retention"
down_revision: str | None = "c7a42e189d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update workspaces table with memory retention settings
    op.add_column(
        "workspaces", sa.Column("memory_retention_days", sa.Integer(), nullable=True)
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "memory_auto_archive_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "memory_retention_action",
            sa.String(length=20),
            nullable=False,
            server_default="archive",
        ),
    )
    op.create_index(
        "ix_workspaces_memory_auto_archive_enabled",
        "workspaces",
        ["memory_auto_archive_enabled"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_workspace_memory_retention_invariant",
        "workspaces",
        "NOT memory_auto_archive_enabled OR ("
        "memory_retention_days IS NOT NULL AND "
        "memory_retention_days > 0 AND "
        "memory_retention_days <= 36500"
        ")",
    )

    # 2. Update workspace_limits table with memory limits
    op.add_column(
        "workspace_limits", sa.Column("max_memory_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "workspace_limits",
        sa.Column("max_memory_bytes", sa.BigInteger(), nullable=True),
    )

    # 3. Update memories table with archived_at column and composite index
    op.add_column(
        "memories", sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_memories_archived_at", "memories", ["archived_at"], unique=False
    )
    op.create_index(
        "ix_memories_archived_at_workspace_id",
        "memories",
        ["archived_at", "workspace_id"],
        unique=False,
    )

    # 4. Seed default memory limits for standard plan tiers
    op.execute(
        "UPDATE workspace_limits SET max_memory_count = 1000, max_memory_bytes = 5000000000 WHERE plan_tier = 'free' AND workspace_id IS NULL"
    )
    op.execute(
        "UPDATE workspace_limits SET max_memory_count = 10000, max_memory_bytes = 50000000000 WHERE plan_tier = 'team' AND workspace_id IS NULL"
    )


def downgrade() -> None:
    # 3. Revert memories changes
    op.drop_index("ix_memories_archived_at_workspace_id", table_name="memories")
    op.drop_index("ix_memories_archived_at", table_name="memories")
    op.drop_column("memories", "archived_at")

    # 2. Revert workspace_limits changes
    op.drop_column("workspace_limits", "max_memory_bytes")
    op.drop_column("workspace_limits", "max_memory_count")

    # 1. Revert workspaces changes
    op.drop_constraint(
        "ck_workspace_memory_retention_invariant", "workspaces", type_="check"
    )
    op.drop_index("ix_workspaces_memory_auto_archive_enabled", table_name="workspaces")
    op.drop_column("workspaces", "memory_retention_action")
    op.drop_column("workspaces", "memory_auto_archive_enabled")
    op.drop_column("workspaces", "memory_retention_days")
