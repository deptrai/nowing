"""social unique constraints become workspace-scoped (Story 21.8)

Revision ID: 211
Revises: 210
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "211"
down_revision: str | None = "210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(text(stmt))


def upgrade() -> None:
    _exec_statements(
        "ALTER TABLE social_monitored_targets DROP CONSTRAINT IF EXISTS uq_social_target;",
        "ALTER TABLE social_posts DROP CONSTRAINT IF EXISTS uq_social_post;",
        "DROP INDEX IF EXISTS idx_social_posts_platform_ext;",
        (
            "ALTER TABLE social_monitored_targets "
            "ADD CONSTRAINT uq_social_target UNIQUE (workspace_id, platform, target_id);"
        ),
        (
            "ALTER TABLE social_posts "
            "ADD CONSTRAINT uq_social_post UNIQUE (workspace_id, platform, external_post_id);"
        ),
        "CREATE INDEX IF NOT EXISTS idx_social_posts_workspace_platform_ext "
        "ON social_posts (workspace_id, platform, external_post_id);",
    )


def downgrade() -> None:
    _exec_statements(
        "ALTER TABLE social_posts DROP CONSTRAINT IF EXISTS uq_social_post;",
        "ALTER TABLE social_monitored_targets DROP CONSTRAINT IF EXISTS uq_social_target;",
        (
            "ALTER TABLE social_posts "
            "ADD CONSTRAINT uq_social_post UNIQUE (platform, external_post_id);"
        ),
        (
            "ALTER TABLE social_monitored_targets "
            "ADD CONSTRAINT uq_social_target UNIQUE (platform, target_id);"
        ),
        "CREATE INDEX IF NOT EXISTS idx_social_posts_platform_ext "
        "ON social_posts (platform, external_post_id);",
        "DROP INDEX IF EXISTS idx_social_posts_workspace_platform_ext;",
    )
