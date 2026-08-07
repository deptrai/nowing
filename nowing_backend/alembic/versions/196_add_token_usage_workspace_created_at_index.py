"""Add composite index on token_usage (workspace_id, created_at).

Revision ID: 196
Revises: 195
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "196"
down_revision: str | None = "195"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite index to speed up usage dashboard date-range queries."""
    op.create_index(
        "ix_token_usage_workspace_created_at",
        "token_usage",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    """Remove the composite index."""
    op.drop_index("ix_token_usage_workspace_created_at", table_name="token_usage")
