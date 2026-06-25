"""135_add_chat_run_heartbeat - Add last_heartbeat_at to chat_runs for multi-worker fence

Revision ID: 135
Revises: 134

Adds last_heartbeat_at TIMESTAMPTZ NULL to chat_runs.
RunEventWriter.run_flush_loop updates this every 30s so mark_abandoned_runs_on_startup
can distinguish healthy runs on sibling workers from truly orphaned runs.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "135"
down_revision: str | None = "134"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    col_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='chat_runs' AND column_name='last_heartbeat_at'"
        )
    ).fetchone()
    if not col_exists:
        op.add_column(
            "chat_runs",
            sa.Column("last_heartbeat_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_runs_heartbeat_running "
        "ON chat_runs(last_heartbeat_at) WHERE status='running'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chat_runs_heartbeat_running")
    op.execute(
        "ALTER TABLE chat_runs DROP COLUMN IF EXISTS last_heartbeat_at"
    )
