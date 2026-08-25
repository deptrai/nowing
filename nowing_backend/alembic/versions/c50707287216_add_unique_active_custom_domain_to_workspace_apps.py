"""add unique active custom domain to workspace_apps

Revision ID: c50707287216
Revises: f984b591d763
Create Date: 2026-08-25 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c50707287216"
down_revision: str | None = "f984b591d763"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Resolve any existing duplicate active custom domains before adding the
    # partial unique index. The most recently updated row is kept active;
    # older duplicates are downgraded to failed so the index can be created.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                custom_domain,
                ROW_NUMBER() OVER (
                    PARTITION BY custom_domain
                    ORDER BY updated_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM workspace_apps
            WHERE custom_domain_status = 'active'
              AND custom_domain IS NOT NULL
        )
        UPDATE workspace_apps
        SET custom_domain_status = 'failed',
            error_message = 'Downgraded by migration: duplicate active custom domain'
        FROM ranked
        WHERE workspace_apps.id = ranked.id
          AND ranked.rn > 1;
        """
    )

    # Partial unique index on active custom domains so CNAME bindings cannot
    # collide across workspaces (Story 27.1c AC-2). NULL/failed rows are
    # excluded, allowing multiple apps to have no custom domain.
    op.create_index(
        "uq_workspace_apps_active_custom_domain",
        "workspace_apps",
        ["custom_domain"],
        unique=True,
        postgresql_where=sa.text("custom_domain_status = 'active'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_workspace_apps_active_custom_domain",
        table_name="workspace_apps",
    )
