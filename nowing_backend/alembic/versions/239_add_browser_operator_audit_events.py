"""add browser operator audit events table

Revision ID: 239
Revises: 8f3b4c1a2d5e
Create Date: 2026-09-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "239"
down_revision: str | None = "8f3b4c1a2d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "browser_operator_audit_events",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "mission_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("dsh_missions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("command_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("challenge", sa.String(64), nullable=True),
        sa.Column("requires_human", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_browser_operator_audit_events")),
    )
    op.create_index(
        op.f("ix_browser_audit_mission"),
        "browser_operator_audit_events",
        ["mission_id"],
    )
    op.create_index(
        op.f("ix_browser_audit_workspace"),
        "browser_operator_audit_events",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_browser_audit_created"),
        "browser_operator_audit_events",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_browser_audit_command_id"),
        "browser_operator_audit_events",
        ["command_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_browser_audit_command_id"), table_name="browser_operator_audit_events"
    )
    op.drop_index(
        op.f("ix_browser_audit_created"), table_name="browser_operator_audit_events"
    )
    op.drop_index(
        op.f("ix_browser_audit_workspace"), table_name="browser_operator_audit_events"
    )
    op.drop_index(
        op.f("ix_browser_audit_mission"), table_name="browser_operator_audit_events"
    )
    op.drop_table("browser_operator_audit_events")
