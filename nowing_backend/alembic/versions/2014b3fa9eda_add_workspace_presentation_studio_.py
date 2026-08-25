"""add workspace presentation studio enabled

Revision ID: 2014b3fa9eda
Revises: 697ee5945395
Create Date: 2026-08-25 20:31:44.776661

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2014b3fa9eda"
down_revision: str | None = "697ee5945395"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "workspaces",
        sa.Column(
            "presentation_studio_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workspaces", "presentation_studio_enabled")
