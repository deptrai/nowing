"""add exa mcp connector

Revision ID: 190
Revises: 189
Create Date: 2026-08-05 10:50:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "190"
down_revision: str | None = "189"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add EXA_MCP_CONNECTOR to SearchSourceConnectorType enum."""
    op.execute(
        """
        ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS 'EXA_MCP_CONNECTOR';
        """
    )


def downgrade() -> None:
    """Removing an enum value from a PostgreSQL enum requires recreating it.

    This is left as a manual operation if needed.
    """
    pass
