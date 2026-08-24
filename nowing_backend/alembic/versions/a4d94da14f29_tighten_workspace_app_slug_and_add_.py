"""tighten workspace_app slug and add global published slug unique index

Revision ID: a4d94da14f29
Revises: 232
Create Date: 2026-08-24 17:48:29.307395

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4d94da14f29'
down_revision: str | None = '232'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # DNS label limit for *.apps.nowing.net subdomains.
    op.alter_column(
        "workspace_apps",
        "slug",
        existing_type=sa.String(length=100),
        type_=sa.String(length=63),
        existing_nullable=False,
    )
    # Globally unique published slug so public URLs cannot collide across workspaces.
    op.create_index(
        "ix_workspace_apps_published_slug",
        "workspace_apps",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_workspace_apps_published_slug",
        table_name="workspace_apps",
    )
    op.alter_column(
        "workspace_apps",
        "slug",
        existing_type=sa.String(length=63),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
