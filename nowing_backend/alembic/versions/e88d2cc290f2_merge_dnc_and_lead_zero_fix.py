"""merge_dnc_and_lead_zero_fix

Revision ID: e88d2cc290f2
Revises: 223, c23594e4faaf
Create Date: 2026-08-17 03:57:35.501982

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'e88d2cc290f2'
down_revision: str | None = ('223', 'c23594e4faaf')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
