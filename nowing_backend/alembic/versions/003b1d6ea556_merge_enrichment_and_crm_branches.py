"""merge enrichment and crm branches

Revision ID: 003b1d6ea556
Revises: 200, 201
Create Date: 2026-08-15 15:09:13.930042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003b1d6ea556'
down_revision: Union[str, None] = ('200', '201')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
