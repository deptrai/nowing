"""add composite index on social posts platform/intent/published (Story 21.8)

Revision ID: 207
Revises: 206
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "207"
down_revision: str | None = "206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_social_posts_platform_intent_published",
        "social_posts",
        ["platform", "intent_tag", "published_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_social_posts_platform_intent_published",
        table_name="social_posts",
    )
