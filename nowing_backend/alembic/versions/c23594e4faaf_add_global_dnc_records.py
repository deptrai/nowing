"""add global dnc records

Revision ID: c23594e4faaf
Revises: 07582243b847
Create Date: 2026-08-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "c23594e4faaf"
down_revision = "07582243b847"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "global_dnc_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=True),
        sa.Column("value_hmac", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_type", "value_hmac", name="uq_global_dnc_entry"),
    )
    op.create_index(
        "ix_global_dnc_records_hmac", "global_dnc_records", ["value_hmac"]
    )
    op.create_index(
        "ix_global_dnc_records_type", "global_dnc_records", ["record_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_global_dnc_records_type", table_name="global_dnc_records")
    op.drop_index("ix_global_dnc_records_hmac", table_name="global_dnc_records")
    op.drop_table("global_dnc_records")
