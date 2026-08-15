"""add outcome pricing, pricing plans, and promo codes (Story 21.7 / AD-42 / AD-48 / FR-69)

Revision ID: 215
Revises: 214
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

from alembic import op

revision: str = "216"
down_revision: str | None = "215"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create outcome_events table
    op.create_table(
        "outcome_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("client_id", postgresql.CITEXT(), nullable=True, index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("attribution", sa.String(100), nullable=False, server_default="direct"),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "outcome_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )

    # 2. Create pricing_plans table
    op.create_table(
        "pricing_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("client_id", postgresql.CITEXT(), nullable=True, index=True),
        sa.Column("plan_type", sa.String(50), nullable=False, server_default="outcome"),
        sa.Column("seat_price", sa.BigInteger(), nullable=True),
        sa.Column(
            "outcome_rates_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
        sa.Column("billing_period", sa.String(20), nullable=True, server_default="monthly"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.UniqueConstraint("workspace_id", name="uq_pricing_plans_workspace_id"),
    )

    # 3. Create promo_codes table
    op.create_table(
        "promo_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("credit_micros_granted", sa.BigInteger(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )

    # 4. Create promo_code_redemptions table
    op.create_table(
        "promo_code_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "promo_code_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("promo_codes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("credit_micros_granted", sa.BigInteger(), nullable=False),
        sa.Column(
            "redeemed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.UniqueConstraint("user_id", "promo_code_id", name="uq_promo_code_redemption_user_code"),
    )

    # 5. Partial unique index on billing_events for outcome_event
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_billing_events_outcome_unique "
            "ON billing_events (event_id) "
            "WHERE event_entity_type = 'outcome_event';"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_billing_events_outcome_unique;"))
    op.drop_table("promo_code_redemptions")
    op.drop_table("promo_codes")
    op.drop_table("pricing_plans")
    op.drop_table("outcome_events")
