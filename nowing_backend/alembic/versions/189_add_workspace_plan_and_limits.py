"""add workspace plan tier and workspace_limits table

Revision ID: 189
Revises: 188
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "189"
down_revision: str | None = "188"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add plan tier to workspaces
    op.add_column(
        "workspaces",
        sa.Column(
            "plan_tier",
            sa.String(20),
            nullable=False,
            server_default="free",
        ),
    )
    op.create_index(
        op.f("ix_workspaces_plan_tier"),
        "workspaces",
        ["plan_tier"],
        unique=False,
    )

    # 2. Create workspace_limits table
    op.create_table(
        "workspace_limits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_tier", sa.String(20), nullable=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("max_documents", sa.Integer(), nullable=True),
        sa.Column("max_members", sa.Integer(), nullable=True),
        sa.Column("max_runs", sa.Integer(), nullable=True),
        sa.Column("max_storage_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "run_period_hours", sa.Integer(), nullable=False, server_default="720"
        ),
        sa.CheckConstraint(
            "(plan_tier IS NOT NULL) OR (workspace_id IS NOT NULL)",
            name="ck_workspace_limits_plan_or_workspace",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_limits")),
    )

    op.create_index(
        op.f("ix_workspace_limits_plan_tier"),
        "workspace_limits",
        ["plan_tier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_limits_workspace_id"),
        "workspace_limits",
        ["workspace_id"],
        unique=False,
    )

    # 3. Partial unique indexes: one default per plan, one override per workspace.
    op.create_index(
        "uq_workspace_limits_plan_default",
        "workspace_limits",
        ["plan_tier"],
        unique=True,
        postgresql_where=sa.text("workspace_id IS NULL"),
    )
    op.create_index(
        "uq_workspace_limits_workspace_override",
        "workspace_limits",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("plan_tier IS NULL"),
    )

    # 4. Seed plan defaults.  These are the source-of-truth values; operators may
    #    update rows directly or via WORKSPACE_PLAN_LIMITS at runtime.
    workspace_limits_table = sa.table(
        "workspace_limits",
        sa.column("plan_tier", sa.String(20)),
        sa.column("workspace_id", sa.Integer),
        sa.column("max_documents", sa.Integer),
        sa.column("max_members", sa.Integer),
        sa.column("max_runs", sa.Integer),
        sa.column("max_storage_bytes", sa.BigInteger),
        sa.column("run_period_hours", sa.Integer),
        sa.column("created_at", sa.TIMESTAMP(timezone=True)),
        sa.column("updated_at", sa.TIMESTAMP(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        workspace_limits_table,
        [
            {
                "plan_tier": "free",
                "workspace_id": None,
                "max_documents": 100,
                "max_members": 3,
                "max_runs": 50,
                "max_storage_bytes": 1_000_000_000,
                "run_period_hours": 720,
                "created_at": now,
                "updated_at": now,
            },
            {
                "plan_tier": "team",
                "workspace_id": None,
                "max_documents": 1000,
                "max_members": 20,
                "max_runs": 500,
                "max_storage_bytes": 10_000_000_000,
                "run_period_hours": 720,
                "created_at": now,
                "updated_at": now,
            },
            {
                "plan_tier": "enterprise",
                "workspace_id": None,
                "max_documents": None,
                "max_members": None,
                "max_runs": None,
                "max_storage_bytes": None,
                "run_period_hours": 720,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )

    # 5. Backfill existing workspaces to the 'free' plan (server default already
    #    does this, but make it explicit and idempotent).
    op.execute(
        sa.text("UPDATE workspaces SET plan_tier = 'free' WHERE plan_tier IS NULL")
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workspace_limits_workspace_override", table_name="workspace_limits"
    )
    op.drop_index("uq_workspace_limits_plan_default", table_name="workspace_limits")
    op.drop_table("workspace_limits")
    op.drop_index(op.f("ix_workspaces_plan_tier"), table_name="workspaces")
    op.drop_column("workspaces", "plan_tier")
