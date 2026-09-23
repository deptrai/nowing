"""merge branches

Revision ID: e84a71b56b48
Revises: 235_lead_indexing_fts_and_vector, 236
Create Date: 2026-09-01 08:07:39.015883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e84a71b56b48'
down_revision: Union[str, None] = ('235_lead_indexing_fts_and_vector', '236')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
