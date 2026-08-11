"""add memories client agent columns and rls

Revision ID: 10127c164b44
Revises: f0ae468377f4
Create Date: 2026-08-10 04:30:14.313359

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '10127c164b44'
down_revision: str | None = 'f0ae468377f4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add client_id/agent_id to memories for vertical-tenant tagging."""
    op.add_column("memories", sa.Column("client_id", sa.Text(), nullable=True))
    op.add_column("memories", sa.Column("agent_id", sa.Text(), nullable=True))

    op.create_index(
        op.f("ix_memories_client_id"),
        "memories",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memories_agent_id"),
        "memories",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memories_workspace_id_client_id"),
        "memories",
        ["workspace_id", "client_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop client_id/agent_id columns and indexes."""
    op.drop_index(
        op.f("ix_memories_workspace_id_client_id"),
        table_name="memories",
    )
    op.drop_index(op.f("ix_memories_agent_id"), table_name="memories")
    op.drop_index(op.f("ix_memories_client_id"), table_name="memories")

    op.drop_column("memories", "agent_id")
    op.drop_column("memories", "client_id")
