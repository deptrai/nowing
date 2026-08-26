"""merge all current heads

Revision ID: 9a32642d01df
Revises: 233, b5cf13c425fb
Create Date: 2026-08-26 18:30:02.459194

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '9a32642d01df'
down_revision: str | None = ('233', 'b5cf13c425fb')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
