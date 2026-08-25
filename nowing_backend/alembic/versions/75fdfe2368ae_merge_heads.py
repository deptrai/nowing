"""merge heads

Revision ID: 75fdfe2368ae
Revises: a4d94da14f29, c50707287216
Create Date: 2026-08-25 17:11:57.286861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75fdfe2368ae'
down_revision: Union[str, None] = ('a4d94da14f29', 'c50707287216')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
