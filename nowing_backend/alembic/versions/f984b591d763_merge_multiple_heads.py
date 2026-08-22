"""merge multiple heads

Revision ID: f984b591d763
Revises: 193_add_playbook_is_approved, c610f68d47fb
Create Date: 2026-08-22 14:03:59.208340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f984b591d763'
down_revision: Union[str, None] = ('193_add_playbook_is_approved', 'c610f68d47fb', '227')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
