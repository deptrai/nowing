"""add unique constraint on leads value_hmac

Revision ID: 224
Revises: 223
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    if table_name not in sa.inspect(bind).get_table_names():
        return False
    return column_name in {
        column["name"] for column in sa.inspect(bind).get_columns(table_name)
    }


revision: str = "224"
down_revision: str | None = "94cfa0f6f5f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not _column_exists("leads", "value_hmac"):
        return
    op.create_index(
        "uq_leads_workspace_value_hmac",
        "leads",
        ["workspace_id", "value_hmac"],
        unique=True,
        postgresql_where=sa.text("value_hmac IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_leads_workspace_value_hmac",
        table_name="leads",
    )
