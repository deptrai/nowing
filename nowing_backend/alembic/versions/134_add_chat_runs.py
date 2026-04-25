"""134_add_chat_runs - Background agent run tracking tables

Revision ID: 134
Revises: 133

Adds chat_runs and chat_run_events tables for persistent background agent
execution. Runs survive FE disconnect, browser refresh, and BE worker restart.
Event log enables replay-on-reconnect and abandoned-run resume.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "134"
down_revision: str | None = "133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- chat_runs table ---
    table_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_runs'"
        )
    ).fetchone()

    if not table_exists:
        op.create_table(
            "chat_runs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("thread_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_by_id", postgresql.UUID(as_uuid=True), nullable=False
            ),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("langgraph_thread_id", sa.String(length=96), nullable=False),
            sa.Column("user_query", sa.Text(), nullable=True),
            sa.Column("llm_config_id", sa.Integer(), nullable=True),
            sa.Column("model_id", sa.Integer(), nullable=True),
            sa.Column(
                "mentioned_document_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "disabled_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default="running",
            ),
            sa.Column("last_event_seq", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "started_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("final_message_id", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.String(length=8000), nullable=True),
            sa.ForeignKeyConstraint(
                ["thread_id"],
                ["new_chat_threads.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"],
                ["user.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["llm_config_id"],
                ["new_llm_configs.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["final_message_id"],
                ["new_chat_messages.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_runs_thread_active "
        "ON chat_runs(thread_id) WHERE status = 'running'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_runs_thread_created "
        "ON chat_runs(thread_id, started_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_runs_status ON chat_runs(status)"
    )

    # --- chat_run_events table ---
    events_table_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_run_events'"
        )
    ).fetchone()

    if not events_table_exists:
        op.create_table(
            "chat_run_events",
            sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column(
                "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["chat_runs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id", "seq", name="uq_chat_run_events_run_seq"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_run_events_run_seq "
        "ON chat_run_events(run_id, seq)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_run_events_event_type "
        "ON chat_run_events(event_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chat_run_events_event_type")
    op.execute("DROP INDEX IF EXISTS idx_chat_run_events_run_seq")
    op.execute("DROP TABLE IF EXISTS chat_run_events")
    op.execute("DROP INDEX IF EXISTS idx_chat_runs_status")
    op.execute("DROP INDEX IF EXISTS idx_chat_runs_thread_created")
    op.execute("DROP INDEX IF EXISTS idx_chat_runs_thread_active")
    op.execute("DROP TABLE IF EXISTS chat_runs")
