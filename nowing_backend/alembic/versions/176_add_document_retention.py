"""Add document retention columns and reconcile zero_publication.

Revision ID: 176
Revises: 175
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.zero_publication import apply_publication

revision: str = "176"
down_revision: str | None = "175"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Workspace retention settings.
    op.add_column(
        "workspaces",
        sa.Column(
            "document_retention_days",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "auto_archive_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "document_retention_action",
            sa.String(20),
            nullable=False,
            server_default="archive",
        ),
    )
    op.create_index(
        "ix_workspaces_auto_archive_enabled",
        "workspaces",
        ["auto_archive_enabled"],
    )

    # Document soft-archive timestamp.
    op.add_column(
        "documents",
        sa.Column(
            "archived_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_documents_archived_at_workspace_id",
        "documents",
        ["archived_at", "workspace_id"],
    )

    # Reconcile Zero publication so archived_at is replicated for real-time sync.
    apply_publication(op.get_bind())


def downgrade() -> None:
    op.drop_index("ix_documents_archived_at_workspace_id", table_name="documents")
    op.drop_column("documents", "archived_at")
    op.drop_index("ix_workspaces_auto_archive_enabled", table_name="workspaces")
    op.drop_column("workspaces", "document_retention_action")
    op.drop_column("workspaces", "auto_archive_enabled")
    op.drop_column("workspaces", "document_retention_days")
