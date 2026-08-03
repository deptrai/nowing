"""Add usage tracking columns to scraper_platform_accounts.

Revision ID: 188
Revises: 187
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "188"
down_revision: str | None = "187"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scraper_platform_accounts",
        sa.Column(
            "last_used_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "scraper_platform_accounts",
        sa.Column(
            "usage_state",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("scraper_platform_accounts", "usage_state")
    op.drop_column("scraper_platform_accounts", "last_used_at")
