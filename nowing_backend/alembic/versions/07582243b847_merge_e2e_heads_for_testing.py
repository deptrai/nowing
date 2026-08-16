"""merge e2e heads for testing

Revision ID: 07582243b847
Revises: 214_dnc, 222
Create Date: 2026-08-16 22:36:20.110631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07582243b847'
down_revision: Union[str, None] = ('214_dnc', '222')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
