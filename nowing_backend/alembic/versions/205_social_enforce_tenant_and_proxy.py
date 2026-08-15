"""social enforce tenant and proxy (Story 21.8)

Revision ID: 205
Revises: 204
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "205"
down_revision: str | None = "204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(text(stmt))


def upgrade() -> None:
    _exec_statements(
        "ALTER TABLE social_monitored_targets ADD COLUMN IF NOT EXISTS proxy_url TEXT;",
    )

    # Backfill workspace_id from the associated target where missing.
    _exec_statements(
        """
        UPDATE social_posts p
        SET workspace_id = t.workspace_id
        FROM social_monitored_targets t
        WHERE p.target_id = t.id
          AND p.workspace_id IS NULL;
        """,
    )

    # Orphan posts that still lack multi-tenancy should not be kept.
    _exec_statements(
        "DELETE FROM social_posts WHERE workspace_id IS NULL OR target_id IS NULL;",
    )

    _exec_statements(
        "ALTER TABLE social_posts ALTER COLUMN workspace_id SET NOT NULL;",
        "ALTER TABLE social_posts ALTER COLUMN target_id SET NOT NULL;",
    )


def downgrade() -> None:
    _exec_statements(
        "ALTER TABLE social_posts ALTER COLUMN target_id DROP NOT NULL;",
        "ALTER TABLE social_posts ALTER COLUMN workspace_id DROP NOT NULL;",
        "ALTER TABLE social_monitored_targets DROP COLUMN IF EXISTS proxy_url;",
    )
