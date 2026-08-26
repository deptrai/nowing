"""merge telemetry and agent memory branches

Revision ID: b5cf13c425fb
Revises: 003b1d6ea556, c416d1048caf
Create Date: 2026-08-26 17:48:57.673287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5cf13c425fb'
down_revision: Union[str, None] = ('003b1d6ea556', 'c416d1048caf')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
