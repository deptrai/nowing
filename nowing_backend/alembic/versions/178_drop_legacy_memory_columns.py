"""Drop legacy memory columns.

Revision ID: 178
Revises: 177

Changes:
1. Drop User.memory_md from both user and user_oauth variants.
2. Drop Workspace.shared_memory_md.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "178"
down_revision: str | None = "177"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE "user" DROP COLUMN IF EXISTS memory_md;
        """
    )
    op.execute(
        """
        ALTER TABLE workspaces DROP COLUMN IF EXISTS shared_memory_md;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE "user" ADD COLUMN IF NOT EXISTS memory_md TEXT DEFAULT '';
        """
    )
    op.execute(
        """
        ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS shared_memory_md TEXT DEFAULT '';
        """
    )
