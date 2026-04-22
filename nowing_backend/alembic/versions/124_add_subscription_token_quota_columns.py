"""124_add_subscription_token_quota_columns

Revision ID: 124
Revises: 123
Create Date: 2026-04-14

Adds subscription and token quota columns to the user table for
cloud-mode LLM billing (Story 3.5).

Columns added:
- monthly_token_limit (Integer, default 100000)
- tokens_used_this_month (Integer, default 0)
- token_reset_date (Date, nullable)
- subscription_status (Enum: free/active/canceled/past_due, default 'free')
- plan_id (String(50), default 'free')
- stripe_customer_id (String(255), nullable, unique)
- stripe_subscription_id (String(255), nullable, unique)

Also creates the 'subscriptionstatus' PostgreSQL enum type.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "124"
down_revision: str | None = "123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Create the enum type so SQLAlchemy's create_type=False works at runtime
subscriptionstatus_enum = sa.Enum(
    "free",
    "active",
    "canceled",
    "past_due",
    name="subscriptionstatus",
)


def upgrade() -> None:
    conn = op.get_bind()

    # Drop any pre-existing subscriptionstatus enum created by SQLAlchemy create_all()
    conn.execute(sa.text("DROP TYPE IF EXISTS subscriptionstatus CASCADE"))
    subscriptionstatus_enum.create(conn, checkfirst=False)

    # Add columns only if they don't already exist (idempotent — handles schema drift)
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS monthly_token_limit INTEGER NOT NULL DEFAULT 100000'
    ))
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS tokens_used_this_month INTEGER NOT NULL DEFAULT 0'
    ))
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS token_reset_date DATE'
    ))
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS subscription_status subscriptionstatus NOT NULL DEFAULT \'free\''
    ))
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS plan_id VARCHAR(50) NOT NULL DEFAULT \'free\''
    ))
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)'
    ))
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255)'
    ))

    # Create unique constraints only if they don't exist
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_stripe_customer_id'
            ) THEN
                ALTER TABLE "user" ADD CONSTRAINT uq_user_stripe_customer_id UNIQUE (stripe_customer_id);
            END IF;
        END $$;
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_stripe_subscription_id'
            ) THEN
                ALTER TABLE "user" ADD CONSTRAINT uq_user_stripe_subscription_id UNIQUE (stripe_subscription_id);
            END IF;
        END $$;
    """))


def downgrade() -> None:
    op.drop_constraint("uq_user_stripe_subscription_id", "user", type_="unique")
    op.drop_constraint("uq_user_stripe_customer_id", "user", type_="unique")
    op.drop_column("user", "stripe_subscription_id")
    op.drop_column("user", "stripe_customer_id")
    op.drop_column("user", "plan_id")
    op.drop_column("user", "subscription_status")
    op.drop_column("user", "token_reset_date")
    op.drop_column("user", "tokens_used_this_month")
    op.drop_column("user", "monthly_token_limit")

    subscriptionstatus_enum.drop(op.get_bind(), checkfirst=True)
