"""Make token_usage.user_id nullable for system-level usage tracking (AI-39.5).

Revision ID: 245
Revises: 244
Create Date: 2026-10-12
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "245"
down_revision: str | None = "244"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "token_usage",
        "user_id",
        existing_type=postgresql.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("DELETE FROM token_usage WHERE user_id IS NULL")
    op.alter_column(
        "token_usage",
        "user_id",
        existing_type=postgresql.UUID(),
        nullable=False,
    )
