"""add_xactions_mcp_connector_enum

Revision ID: 5bd0001357ae
Revises: a44ca7ffbb4f
Create Date: 2026-09-09 19:46:19.673041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bd0001357ae'
down_revision: Union[str, None] = 'a44ca7ffbb4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add XACTIONS_MCP_CONNECTOR to SearchSourceConnectorType enum."""
    with op.get_context().autocommit_block():
        op.execute(
            """
            ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS 'XACTIONS_MCP_CONNECTOR';
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    pass
