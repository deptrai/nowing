"""add credit_purchases status completed_at index

Revision ID: c416d1048caf
Revises: f984b591d763
Create Date: 2026-08-26 17:30:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c416d1048caf"
down_revision: str | None = "f984b591d763"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite index on credit_purchases(status, completed_at)."""
    op.create_index(
        "ix_credit_purchases_status_completed_at",
        "credit_purchases",
        ["status", "completed_at"],
    )


def downgrade() -> None:
    """Drop the composite index on credit_purchases(status, completed_at)."""
    op.drop_index(
        "ix_credit_purchases_status_completed_at",
        table_name="credit_purchases",
    )
