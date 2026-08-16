"""fix_lead_tables_zero_sync_client_id_and_updated_at

Revision ID: 94cfa0f6f5f9
Revises: e88d2cc290f2
Create Date: 2026-08-17 03:57:56.190101

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op
from app.zero_publication import apply_publication

# revision identifiers, used by Alembic.
revision: str = '94cfa0f6f5f9'
down_revision: str | None = 'e88d2cc290f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ZERO_TABLES = (
    "leads",
    "lead_pipeline_stages",
    "lead_assignments",
    "lead_activity_logs",
)


def _column_type(conn, table: str, column: str) -> str | None:
    row = conn.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    ).fetchone()
    return row[0] if row else None


def _publication_exists(conn) -> bool:
    row = conn.execute(
        text("SELECT pubname FROM pg_publication WHERE pubname = 'zero_publication'")
    ).fetchone()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()

    # Remove the lead tables from zero_publication while we alter their columns.
    # Postgres forbids ALTER COLUMN ... TYPE on a column that a publication
    # depends on, so we drop and re-add them at the end.
    if _publication_exists(bind):
        bind.execute(
            text(
                "ALTER PUBLICATION \"zero_publication\" DROP TABLE "
                + ", ".join(f"\"{t}\"" for t in _ZERO_TABLES)
            )
        )

    # Add missing updated_at to leads so it can be published by zero_publication.
    if _column_type(bind, "leads", "updated_at") is None:
        op.add_column(
            "leads",
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )

    # Cast client_id from citext to text for the lead tables that are synced by
    # Zero. Zero does not support the citext type, so these columns were failing
    # the zero_publication sync.
    for table in _ZERO_TABLES:
        if _column_type(bind, table, "client_id") == "citext":
            bind.execute(
                text(f'ALTER TABLE "{table}" ALTER COLUMN client_id TYPE text USING client_id::text')
            )

    # Reconcile zero_publication to the canonical shape now that the columns are
    # Zero-compatible and leads has the required updated_at column.
    apply_publication(bind)


def downgrade() -> None:
    bind = op.get_bind()

    if _publication_exists(bind):
        bind.execute(
            text(
                "ALTER PUBLICATION \"zero_publication\" DROP TABLE "
                + ", ".join(f"\"{t}\"" for t in _ZERO_TABLES)
            )
        )

    for table in _ZERO_TABLES:
        if _column_type(bind, table, "client_id") == "text":
            bind.execute(
                text(f'ALTER TABLE "{table}" ALTER COLUMN client_id TYPE citext USING client_id::citext')
            )

    if _column_type(bind, "leads", "updated_at") is not None:
        op.drop_column("leads", "updated_at")

    apply_publication(bind)
