"""add meeting_minutes table

Revision ID: 233
Revises: 2014b3fa9eda
Create Date: 2026-08-26 03:45:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "233"
down_revision: str | None = "2014b3fa9eda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "meeting_minutes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("audio_source_url", sa.Text(), nullable=True),
        sa.Column("processing_task_id", sa.String(length=255), nullable=True),
        sa.Column(
            "transcript",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column(
            "action_items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_transcript", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["new_chat_threads.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meeting_minutes_status",
        "meeting_minutes",
        ["status"],
    )
    op.create_index(
        "ix_meeting_minutes_workspace_id",
        "meeting_minutes",
        ["workspace_id"],
    )
    op.create_index(
        "ix_meeting_minutes_thread_id",
        "meeting_minutes",
        ["thread_id"],
    )
    op.create_index(
        "ix_meeting_minutes_document_id",
        "meeting_minutes",
        ["document_id"],
    )
    op.create_index(
        "ix_meeting_minutes_processing_task_id",
        "meeting_minutes",
        ["processing_task_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_meeting_minutes_processing_task_id", table_name="meeting_minutes")
    op.drop_index("ix_meeting_minutes_document_id", table_name="meeting_minutes")
    op.drop_index("ix_meeting_minutes_thread_id", table_name="meeting_minutes")
    op.drop_index("ix_meeting_minutes_workspace_id", table_name="meeting_minutes")
    op.drop_index("ix_meeting_minutes_status", table_name="meeting_minutes")
    op.drop_table("meeting_minutes")
