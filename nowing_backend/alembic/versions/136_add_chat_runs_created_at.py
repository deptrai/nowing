"""136_add_chat_runs_created_at - Add missing created_at column to chat_runs

Revision ID: 136
Revises: 135

ChatRun ORM model inherits TimestampMixin which adds created_at, but migration
134 did not include this column. Add it with server_default=now() so existing rows
get a sensible timestamp.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "136"
down_revision: str | None = "135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    col_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='chat_runs' AND column_name='created_at'"
        )
    ).fetchone()
    if not col_exists:
        op.add_column(
            "chat_runs",
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )


def downgrade() -> None:
    op.execute("ALTER TABLE chat_runs DROP COLUMN IF EXISTS created_at")
