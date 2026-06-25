"""132_add_gift_codes_tables

Revision ID: 132
Revises: 131
Create Date: 2026-04-17

Adds gift_codes and gift_requests tables for the Gift Subscription feature
(Epic 6). gift_codes stores Stripe-purchased codes; gift_requests tracks the
admin-approval fallback when Stripe is not configured.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "132"
down_revision: str | None = "131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create gift_codes and gift_requests tables with supporting enums."""
    conn = op.get_bind()

    gift_code_status_enum = postgresql.ENUM(
        "active",
        "redeemed",
        "expired",
        "cancelled",
        name="giftcodestatus",
        create_type=False,
    )
    gift_code_status_enum.create(conn, checkfirst=True)

    gift_request_status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="giftrequeststatus",
        create_type=False,
    )
    gift_request_status_enum.create(conn, checkfirst=True)

    gift_codes_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'gift_codes'"
        )
    ).fetchone()
    if not gift_codes_exists:
        op.create_table(
            "gift_codes",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("plan_id", sa.String(length=50), nullable=False),
            sa.Column("duration_months", sa.Integer(), nullable=False),
            sa.Column("amount_paid", sa.Integer(), nullable=False),
            sa.Column("purchaser_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "stripe_payment_intent_id",
                sa.String(length=255),
                nullable=True,
            ),
            sa.Column("redeemer_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "active",
                    "redeemed",
                    "expired",
                    "cancelled",
                    name="giftcodestatus",
                    create_type=False,
                ),
                nullable=False,
                server_default=sa.text("'active'::giftcodestatus"),
            ),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("redeemed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["purchaser_id"], ["user.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["redeemer_id"], ["user.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_gift_codes_code"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gift_codes_purchaser_id "
        "ON gift_codes (purchaser_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gift_codes_created_at "
        "ON gift_codes (created_at)"
    )
    # Partial unique index: webhook idempotency — duplicate Stripe payment
    # intent deliveries must not create duplicate gift codes. NULL allowed
    # (for admin-fallback / pre-webhook rows) by using a partial WHERE clause.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_gift_codes_stripe_payment_intent_id "
        "ON gift_codes (stripe_payment_intent_id) "
        "WHERE stripe_payment_intent_id IS NOT NULL"
    )

    gift_requests_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'gift_requests'"
        )
    ).fetchone()
    if not gift_requests_exists:
        op.create_table(
            "gift_requests",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("plan_id", sa.String(length=50), nullable=False),
            sa.Column("duration_months", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "pending",
                    "approved",
                    "rejected",
                    name="giftrequeststatus",
                    create_type=False,
                ),
                nullable=False,
                server_default=sa.text("'pending'::giftrequeststatus"),
            ),
            sa.Column("gift_code_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["gift_code_id"], ["gift_codes.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gift_requests_user_id "
        "ON gift_requests (user_id)"
    )


def downgrade() -> None:
    """Drop gift_requests and gift_codes tables and supporting enums."""
    op.execute("DROP INDEX IF EXISTS ix_gift_requests_user_id")
    op.execute("DROP TABLE IF EXISTS gift_requests")
    op.execute("DROP INDEX IF EXISTS uq_gift_codes_stripe_payment_intent_id")
    op.execute("DROP INDEX IF EXISTS ix_gift_codes_created_at")
    op.execute("DROP INDEX IF EXISTS ix_gift_codes_purchaser_id")
    op.execute("DROP TABLE IF EXISTS gift_codes")

    # CASCADE to be safe if future migrations reference these enums
    op.execute("DROP TYPE IF EXISTS giftrequeststatus CASCADE")
    op.execute("DROP TYPE IF EXISTS giftcodestatus CASCADE")
