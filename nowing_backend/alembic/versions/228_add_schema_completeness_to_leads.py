"""add schema_completeness_score, needs_enrichment, and area to leads

Revision ID: 228
Revises: c9f674b89fed
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.zero_publication import apply_publication

revision: str = "228"
down_revision: str | None = "c9f674b89fed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    if table_name not in sa.inspect(bind).get_table_names():
        return False
    return column_name in {
        column["name"] for column in sa.inspect(bind).get_columns(table_name)
    }


def upgrade() -> None:
    if not _column_exists("leads", "schema_completeness_score"):
        op.add_column(
            "leads",
            sa.Column("schema_completeness_score", sa.Float(), nullable=True),
        )
    if not _column_exists("leads", "needs_enrichment"):
        op.add_column(
            "leads",
            sa.Column(
                "needs_enrichment",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not _column_exists("leads", "area"):
        op.add_column(
            "leads",
            sa.Column("area", sa.Float(), nullable=True),
        )

    # Index the enrichment queue filter.
    op.create_index(
        "ix_leads_needs_enrichment",
        "leads",
        ["needs_enrichment"],
        postgresql_where=sa.text("needs_enrichment = true"),
        if_not_exists=True,
    )

    # Reconcile the Zero publication so the new columns are replicated.
    apply_publication(op.get_bind())


def downgrade() -> None:
    op.drop_index("ix_leads_needs_enrichment", table_name="leads", if_exists=True)
    op.drop_column("leads", "area")
    op.drop_column("leads", "needs_enrichment")
    op.drop_column("leads", "schema_completeness_score")
