"""add zalo app secret (Story 21.6 / AD-41)

Revision ID: 213
Revises: 212
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "213"
down_revision: str | None = "212"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        text(
            "ALTER TABLE zalo_connections "
            "ADD COLUMN IF NOT EXISTS app_secret_encrypted TEXT;"
        )
    )


def downgrade() -> None:
    op.execute(
        text(
            "ALTER TABLE zalo_connections "
            "DROP COLUMN IF EXISTS app_secret_encrypted;"
        )
    )
