"""merge story 26.1 with 225

Revision ID: 6be2697f4dfa
Revises: 225, ac475d54f6a2
Create Date: 2026-08-17 20:54:48.294333

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6be2697f4dfa'
down_revision: Union[str, None] = ('225', 'ac475d54f6a2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
