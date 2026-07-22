"""Add workspace_mcp_tool_settings table.

Revision ID: 175
Revises: 174
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "175"
down_revision: str | None = "174"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_mcp_tool_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(120), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "tool_name", name="uq_workspace_mcp_tool"
        ),
    )
    op.create_index(
        "ix_workspace_mcp_tool_settings_workspace_id",
        "workspace_mcp_tool_settings",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_mcp_tool_settings_tool_name",
        "workspace_mcp_tool_settings",
        ["tool_name"],
    )


def downgrade() -> None:
    op.drop_table("workspace_mcp_tool_settings")
