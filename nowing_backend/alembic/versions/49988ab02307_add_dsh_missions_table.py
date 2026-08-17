"""add dsh_missions table

Revision ID: 49988ab02307
Revises: 6be2697f4dfa
Create Date: 2026-08-17 23:23:43.470121

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "49988ab02307"
down_revision: str | None = "6be2697f4dfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "dsh_missions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("mission_type", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="pending", nullable=False
        ),
        sa.Column("phase", sa.String(length=32), nullable=True),
        sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=True),
        sa.Column("current_subtask_id", sa.String(length=64), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "checkpoint",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text('\'{"phase": "crawl", "subtasks": []}\'::jsonb'),
            nullable=False,
        ),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'error', 'cancelled', 'dlq')",
            name="chk_dsh_missions_status",
        ),
        sa.CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
            name="chk_dsh_missions_progress_percent",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dsh_missions_created_at"), "dsh_missions", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_dsh_missions_status"), "dsh_missions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_dsh_missions_updated_at"), "dsh_missions", ["updated_at"], unique=False
    )
    op.create_index(
        op.f("ix_dsh_missions_user_id"), "dsh_missions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_dsh_missions_workspace_id"),
        "dsh_missions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_dsh_missions_workspace_id_status",
        "dsh_missions",
        ["workspace_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_dsh_missions_workspace_id_status", table_name="dsh_missions")
    op.drop_index(op.f("ix_dsh_missions_workspace_id"), table_name="dsh_missions")
    op.drop_index(op.f("ix_dsh_missions_user_id"), table_name="dsh_missions")
    op.drop_index(op.f("ix_dsh_missions_updated_at"), table_name="dsh_missions")
    op.drop_index(op.f("ix_dsh_missions_status"), table_name="dsh_missions")
    op.drop_index(op.f("ix_dsh_missions_created_at"), table_name="dsh_missions")
    op.drop_table("dsh_missions")
