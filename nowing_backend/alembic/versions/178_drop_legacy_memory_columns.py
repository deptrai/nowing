"""Drop legacy memory columns.

Revision ID: 178
Revises: 177

Changes:
1. Drop User.memory_md from both user and user_oauth variants.
2. Drop Workspace.shared_memory_md.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "178"
down_revision: str | None = "177"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Safety guard (Story 3-10b / G1.2) ---------------------------------
    # Refuse to drop the legacy markdown-memory columns while they still hold
    # data that has NOT been backfilled into the structured `memories` table
    # (created by migration 177). Embeddings cannot be generated inside a raw
    # migration, so the backfill lives in an app-level command; run it first:
    #     python scripts/backfill_legacy_memory.py
    # This makes the drop fail-safe: on a DB with no legacy data (or after a
    # successful backfill) the guard is a no-op; otherwise the migration aborts
    # instead of silently destroying user/team memory.
    bind = op.get_bind()

    unmigrated_users = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM "user" u
            WHERE u.memory_md IS NOT NULL AND btrim(u.memory_md) <> ''
              AND NOT EXISTS (
                  SELECT 1 FROM memories m
                  WHERE m.created_by_id = u.id AND m.workspace_id IS NULL
              )
            """
        )
    ).scalar()

    unmigrated_workspaces = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM workspaces w
            WHERE w.shared_memory_md IS NOT NULL AND btrim(w.shared_memory_md) <> ''
              AND NOT EXISTS (
                  SELECT 1 FROM memories m WHERE m.workspace_id = w.id
              )
            """
        )
    ).scalar()

    if (unmigrated_users or 0) > 0 or (unmigrated_workspaces or 0) > 0:
        raise RuntimeError(
            "Migration 178 aborted: refusing to drop legacy memory columns while "
            f"{unmigrated_users} user(s) and {unmigrated_workspaces} workspace(s) still "
            "have non-empty memory_md/shared_memory_md with no backfilled `memories` rows. "
            "Run `python scripts/backfill_legacy_memory.py` first (Story 3-10b), then re-apply."
        )

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
