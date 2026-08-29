"""merge 235 and 4c04

Revision ID: bcf2ac4cf89d
Revises: 235, 4c04ec8dda06
Create Date: 2026-08-27 20:44:39.394336

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'bcf2ac4cf89d'
down_revision: str | Sequence[str] | None = ('235', '4c04ec8dda06')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
