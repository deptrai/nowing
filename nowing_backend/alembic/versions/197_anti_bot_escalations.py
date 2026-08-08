"""add anti_bot_escalations table

Revision ID: 197
Revises: 196
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "197"
down_revision: str | None = "196"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anti_bot_escalations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("capability", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(500), nullable=False),
        sa.Column("block_type", sa.String(50), nullable=False),
        sa.Column("screenshot_url", sa.String(2048), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "detection_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anti_bot_escalations")),
    )

    op.create_index(
        op.f("ix_anti_bot_escalations_run_id"),
        "anti_bot_escalations",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_anti_bot_escalations_workspace_id"),
        "anti_bot_escalations",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_anti_bot_escalations_created_at"),
        "anti_bot_escalations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_anti_bot_escalations_workspace_domain_cap_status",
        "anti_bot_escalations",
        ["workspace_id", "domain", "capability", "status"],
        unique=False,
    )
    op.create_index(
        "ix_anti_bot_escalations_status_created_at",
        "anti_bot_escalations",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_anti_bot_escalations_status_created_at",
        table_name="anti_bot_escalations",
    )
    op.drop_index(
        "ix_anti_bot_escalations_workspace_domain_cap_status",
        table_name="anti_bot_escalations",
    )
    op.drop_index(
        op.f("ix_anti_bot_escalations_created_at"),
        table_name="anti_bot_escalations",
    )
    op.drop_index(
        op.f("ix_anti_bot_escalations_workspace_id"),
        table_name="anti_bot_escalations",
    )
    op.drop_index(
        op.f("ix_anti_bot_escalations_run_id"),
        table_name="anti_bot_escalations",
    )
    op.drop_table("anti_bot_escalations")
