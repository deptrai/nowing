"""add partner payout reconciliation columns

Revision ID: 218
Revises: 217
Create Date: 2026-08-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "218"
down_revision: str | None = "217"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add hold_balance_micros to affiliate_partners
    op.add_column(
        "affiliate_partners",
        sa.Column(
            "hold_balance_micros",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )

    # 2. Add reconciliation, tax and HMAC audit columns to partner_payouts
    op.add_column(
        "partner_payouts",
        sa.Column(
            "tax_deducted_micros",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "partner_payouts",
        sa.Column(
            "net_amount_micros",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "partner_payouts",
        sa.Column(
            "tax_code",
            sa.String(50),
            nullable=True,
        ),
    )
    op.add_column(
        "partner_payouts",
        sa.Column(
            "napas_ref",
            sa.String(100),
            nullable=True,
        ),
    )
    op.add_column(
        "partner_payouts",
        sa.Column(
            "hmac_audit_hash",
            sa.String(128),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("partner_payouts", "hmac_audit_hash")
    op.drop_column("partner_payouts", "napas_ref")
    op.drop_column("partner_payouts", "tax_code")
    op.drop_column("partner_payouts", "net_amount_micros")
    op.drop_column("partner_payouts", "tax_deducted_micros")
    op.drop_column("affiliate_partners", "hold_balance_micros")
