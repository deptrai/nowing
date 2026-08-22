"""add workspace retention check constraint

Revision ID: c9f674b89fed
Revises: d33c362fa627
Create Date: 2026-08-23 04:13:41.141898

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c9f674b89fed'
down_revision: str | None = 'd33c362fa627'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the workspace retention invariant as a CHECK constraint."""
    op.create_check_constraint(
        "ck_workspace_retention_invariant",
        "workspaces",
        "NOT auto_archive_enabled OR ("
        "document_retention_days IS NOT NULL AND "
        "document_retention_days > 0 AND "
        "document_retention_days <= 36500"
        ")",
        postgresql_not_valid=True,
    )
    # Validate existing rows. If any legacy row violates the invariant, this
    # will fail and must be reconciled before the migration can complete.
    op.execute(
        "ALTER TABLE workspaces VALIDATE CONSTRAINT ck_workspace_retention_invariant"
    )


def downgrade() -> None:
    """Drop the workspace retention invariant CHECK constraint."""
    op.drop_constraint(
        "ck_workspace_retention_invariant",
        "workspaces",
        type_="check",
    )
