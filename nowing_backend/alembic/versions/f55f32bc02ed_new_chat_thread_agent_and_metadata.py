"""new_chat_thread_agent_and_metadata

Revision ID: f55f32bc02ed
Revises: 78f7a9b1e85f
Create Date: 2026-08-10 02:06:26.711041

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f55f32bc02ed"
down_revision: str | None = "78f7a9b1e85f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add agent_id and platform_metadata to new_chat_threads."""
    op.add_column(
        "new_chat_threads",
        sa.Column("agent_id", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_new_chat_threads_agent_id"),
        "new_chat_threads",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_new_chat_threads_workspace_id_client_id"),
        "new_chat_threads",
        ["workspace_id", "client_id"],
        unique=False,
    )
    op.add_column(
        "new_chat_threads",
        sa.Column("platform_metadata", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove agent_id and platform_metadata from new_chat_threads."""
    op.drop_column("new_chat_threads", "platform_metadata")
    op.drop_index(
        op.f("ix_new_chat_threads_workspace_id_client_id"),
        table_name="new_chat_threads",
    )
    op.drop_index(op.f("ix_new_chat_threads_agent_id"), table_name="new_chat_threads")
    op.drop_column("new_chat_threads", "agent_id")
