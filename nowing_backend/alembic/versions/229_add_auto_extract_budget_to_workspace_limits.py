"""add auto-extract budget columns to workspace_limits

Revision ID: 229
Revises: 228
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "229"
down_revision: str | None = "228"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    from sqlalchemy.engine import reflection

    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    table_name = "workspace_limits"
    columns = [
        ("auto_extract_item_cap", sa.Integer(), True),
        ("auto_extract_spend_cap_micros", sa.BigInteger(), True),
        ("auto_extract_wallet_pre_check", sa.Boolean(), True),
    ]
    for name, col_type, nullable in columns:
        if not _column_exists(table_name, name):
            op.add_column(table_name, sa.Column(name, col_type, nullable=nullable))


def downgrade() -> None:
    table_name = "workspace_limits"
    for name, _, _ in [
        ("auto_extract_item_cap", None, None),
        ("auto_extract_spend_cap_micros", None, None),
        ("auto_extract_wallet_pre_check", None, None),
    ]:
        if _column_exists(table_name, name):
            op.drop_column(table_name, name)
