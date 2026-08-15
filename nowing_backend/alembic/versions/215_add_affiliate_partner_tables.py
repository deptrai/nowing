"""add affiliate partner tables (Story 21.18 / FR-88 / AD-42)

Revision ID: 215
Revises: 214
Create Date: 2026-08-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "215"
down_revision: str | None = "214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create affiliate_partners table
    op.create_table(
        "affiliate_partners",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("referral_code", CITEXT(), nullable=False, unique=True),
        sa.Column(
            "partner_type", sa.String(50), nullable=False, server_default="agency"
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("commission_rate", sa.Float(), nullable=False, server_default="0.15"),
        sa.Column(
            "balance_micros", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_earned_micros", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_paid_micros", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "payout_method", sa.String(30), nullable=False, server_default="vietqr"
        ),
        sa.Column(
            "payout_details",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_affiliate_partners_user_id", "affiliate_partners", ["user_id"])
    op.create_index(
        "ix_affiliate_partners_referral_code", "affiliate_partners", ["referral_code"]
    )

    # 2. Create partner_referrals table
    op.create_table(
        "partner_referrals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "partner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referred_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "attribution_source",
            sa.String(100),
            nullable=True,
            server_default="direct_ref",
        ),
        sa.Column("landing_page", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_partner_referrals_partner_id", "partner_referrals", ["partner_id"]
    )
    op.create_index(
        "ix_partner_referrals_referred_user_id",
        "partner_referrals",
        ["referred_user_id"],
    )

    # 3. Create partner_commissions table
    op.create_table(
        "partner_commissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "partner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referral_id",
            UUID(as_uuid=True),
            sa.ForeignKey("partner_referrals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credit_purchase_id",
            UUID(as_uuid=True),
            sa.ForeignKey("credit_purchases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_amount_micros", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "commission_micros", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("commission_rate", sa.Float(), nullable=False, server_default="0.15"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(20), nullable=False, server_default="settled"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_partner_commissions_partner_id", "partner_commissions", ["partner_id"]
    )
    op.create_index(
        "ix_partner_commissions_referral_id", "partner_commissions", ["referral_id"]
    )
    op.create_index(
        "ix_partner_commissions_credit_purchase_id",
        "partner_commissions",
        ["credit_purchase_id"],
    )

    # 4. Create partner_payouts table
    op.create_table(
        "partner_payouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "partner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column(
            "payout_method", sa.String(30), nullable=False, server_default="vietqr"
        ),
        sa.Column(
            "payout_details",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("tx_reference", sa.String(255), nullable=True),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_partner_payouts_partner_id", "partner_payouts", ["partner_id"])
    op.create_index("ix_partner_payouts_status", "partner_payouts", ["status"])


def downgrade() -> None:
    op.drop_table("partner_payouts")
    op.drop_table("partner_commissions")
    op.drop_table("partner_referrals")
    op.drop_table("affiliate_partners")
