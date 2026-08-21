"""Add is_approved to playbooks and partial unique index for system playbooks.

Revision ID: 193_add_playbook_is_approved
Revises: 47537dffa86b
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "193_add_playbook_is_approved"
down_revision: str | None = "47537dffa86b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE playbooks
        ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT true
        """
    )

    op.create_index(
        op.f("ix_playbooks_is_approved"),
        "playbooks",
        ["is_approved"],
        if_not_exists=True,
    )

    op.create_index(
        "uq_playbooks_name_scope_system",
        "playbooks",
        ["name", "scope"],
        unique=True,
        postgresql_where=sa.text("workspace_id IS NULL"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_playbooks_name_scope_system",
        table_name="playbooks",
        if_exists=True,
    )
    op.drop_index(
        op.f("ix_playbooks_is_approved"),
        table_name="playbooks",
        if_exists=True,
    )
    op.execute(
        "ALTER TABLE playbooks DROP COLUMN IF EXISTS is_approved"
    )
