"""add custom_domain_verify_token to workspace_apps

Revision ID: 8f3b4c1a2d5e
Revises: da41e2aa02d9
Create Date: 2026-09-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :table"
        ),
        {"table": table},
    ).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    ).fetchone()
    return row is not None


# revision identifiers, used by Alembic.
revision: str = "8f3b4c1a2d5e"
down_revision: str | None = "da41e2aa02d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if not _table_exists(conn, "workspace_apps"):
        return
    if not _column_exists(conn, "workspace_apps", "custom_domain_verify_token"):
        op.add_column(
            "workspace_apps",
            sa.Column("custom_domain_verify_token", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if not _table_exists(conn, "workspace_apps"):
        return
    if _column_exists(conn, "workspace_apps", "custom_domain_verify_token"):
        op.drop_column("workspace_apps", "custom_domain_verify_token")
