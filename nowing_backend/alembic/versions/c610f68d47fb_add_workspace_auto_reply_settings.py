"""add workspace auto reply settings

Revision ID: c610f68d47fb
Revises: 222
Create Date: 2026-08-22 03:00:00.000000

"""
from collections.abc import Sequence

from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c610f68d47fb"
down_revision: str | None = "222"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        Column("auto_reply_enabled", Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "workspaces",
        Column(
            "auto_reply_collections",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "workspaces",
        Column("auto_reply_fallback", Text, nullable=True),
    )
    op.add_column(
        "workspaces",
        Column("auto_reply_recipient_chat_id", String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "auto_reply_recipient_chat_id")
    op.drop_column("workspaces", "auto_reply_fallback")
    op.drop_column("workspaces", "auto_reply_collections")
    op.drop_column("workspaces", "auto_reply_enabled")
