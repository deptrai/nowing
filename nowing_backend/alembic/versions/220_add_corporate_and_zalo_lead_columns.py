"""add corporate verification and zalo status columns to leads

Revision ID: 220
Revises: 218
Create Date: 2026-08-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "220"
down_revision: str | None = "218"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add corporate verification and Zalo active status columns to leads table
    op.add_column(
        "leads",
        sa.Column(
            "tax_id",
            sa.String(50),
            nullable=True,
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "legal_representative",
            sa.String(200),
            nullable=True,
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "charter_capital_vnd",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "company_status",
            sa.String(100),
            nullable=True,
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "is_zalo_active",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # 2. Add index on tax_id for fast B2B registry lookup
    op.create_index(
        "ix_leads_tax_id",
        "leads",
        ["tax_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_leads_tax_id", table_name="leads")
    op.drop_column("leads", "is_zalo_active")
    op.drop_column("leads", "company_status")
    op.drop_column("leads", "charter_capital_vnd")
    op.drop_column("leads", "legal_representative")
    op.drop_column("leads", "tax_id")
