"""add subscription_changes table and expand workspace_limits (Story 29.3 / FR-102)

Revision ID: e5f8a1b2c3d4
Revises: d4e7f1a2b5c8
Create Date: 2026-09-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f8a1b2c3d4"
down_revision: str | None = "d4e7f1a2b5c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0. Ensure updated_at exists on workspace_limits (TimestampMixin)
    op.execute(
        sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'workspace_limits' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE workspace_limits ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now();
                END IF;
            END $$;
        """)
    )

    # 1. Expand workspace_limits with plan catalog & pricing columns (AD-8, AD-51, PM-1)
    op.add_column(
        "workspace_limits",
        sa.Column("max_monthly_credits", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "workspace_limits",
        sa.Column("max_sources", sa.Integer(), nullable=True),
    )
    op.add_column(
        "workspace_limits",
        sa.Column("support_level", sa.String(50), nullable=True),
    )
    op.add_column(
        "workspace_limits",
        sa.Column("price_micros", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "workspace_limits",
        sa.Column(
            "currency",
            sa.String(3),
            nullable=True,
            server_default=sa.text("'USD'"),
        ),
    )

    # 2. Create subscription_changes table (FR-102, PM-4..PM-6)
    op.create_table(
        "subscription_changes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_plan", sa.String(20), nullable=False),
        sa.Column("to_plan", sa.String(20), nullable=False),
        sa.Column("effective_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("reversible_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "initiated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payment_method_id", sa.String(255), nullable=True),
        sa.Column(
            "immediate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "diff_payload",
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

    op.create_index(
        "ix_subscription_changes_workspace_id",
        "subscription_changes",
        ["workspace_id"],
    )
    op.create_index(
        "ix_subscription_changes_status",
        "subscription_changes",
        ["status"],
    )
    op.create_index(
        "ix_subscription_changes_effective_at",
        "subscription_changes",
        ["effective_at"],
    )
    op.create_index(
        "ix_subscription_changes_initiated_by",
        "subscription_changes",
        ["initiated_by"],
    )

    # 3. Seed / update system default plan tiers
    op.execute(
        sa.text("""
            INSERT INTO workspace_limits (
                plan_tier, workspace_id, max_documents, max_members, max_runs,
                max_storage_bytes, max_memory_count, max_memory_bytes, run_period_hours,
                max_monthly_credits, max_sources, support_level, price_micros, currency,
                created_at, updated_at
            )
            SELECT 'free', NULL, 100, 3, 50, 1000000000, 1000, 5000000000, 720,
                   1000000, 2, 'community', 0, 'USD', now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM workspace_limits WHERE plan_tier = 'free' AND workspace_id IS NULL
            )
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO workspace_limits (
                plan_tier, workspace_id, max_documents, max_members, max_runs,
                max_storage_bytes, max_memory_count, max_memory_bytes, run_period_hours,
                max_monthly_credits, max_sources, support_level, price_micros, currency,
                created_at, updated_at
            )
            SELECT 'team', NULL, 1000, 20, 500, 10000000000, 10000, 50000000000, 720,
                   10000000, 10, 'email', 29000000, 'USD', now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM workspace_limits WHERE plan_tier = 'team' AND workspace_id IS NULL
            )
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO workspace_limits (
                plan_tier, workspace_id, max_documents, max_members, max_runs,
                max_storage_bytes, max_memory_count, max_memory_bytes, run_period_hours,
                max_monthly_credits, max_sources, support_level, price_micros, currency,
                created_at, updated_at
            )
            SELECT 'enterprise', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 720,
                   NULL, NULL, 'dedicated', 299000000, 'USD', now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM workspace_limits WHERE plan_tier = 'enterprise' AND workspace_id IS NULL
            )
        """)
    )
    op.execute(
        sa.text("""
            INSERT INTO workspace_limits (
                plan_tier, workspace_id, max_documents, max_members, max_runs,
                max_storage_bytes, max_memory_count, max_memory_bytes, run_period_hours,
                max_monthly_credits, max_sources, support_level, price_micros, currency,
                created_at, updated_at
            )
            SELECT 'growth', NULL, 5000, 50, 2500, 50000000000, 50000, 250000000000, 720,
                   50000000, 25, 'priority', 79000000, 'USD', now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM workspace_limits WHERE plan_tier = 'growth' AND workspace_id IS NULL
            )
        """)
    )
    op.execute(
        sa.text("""
            UPDATE workspace_limits
            SET max_monthly_credits = 1000000,
                max_sources = 2,
                support_level = 'community',
                price_micros = 0,
                currency = 'USD'
            WHERE plan_tier = 'free' AND workspace_id IS NULL
        """)
    )
    op.execute(
        sa.text("""
            UPDATE workspace_limits
            SET max_monthly_credits = 10000000,
                max_sources = 10,
                support_level = 'email',
                price_micros = 29000000,
                currency = 'USD'
            WHERE plan_tier = 'team' AND workspace_id IS NULL
        """)
    )
    op.execute(
        sa.text("""
            UPDATE workspace_limits
            SET support_level = 'dedicated',
                price_micros = 299000000,
                currency = 'USD'
            WHERE plan_tier = 'enterprise' AND workspace_id IS NULL
        """)
    )
    op.execute(
        sa.text("""
            UPDATE workspace_limits
            SET max_monthly_credits = 50000000,
                max_sources = 25,
                support_level = 'priority',
                price_micros = 79000000,
                currency = 'USD'
            WHERE plan_tier = 'growth' AND workspace_id IS NULL
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_changes_initiated_by", table_name="subscription_changes")
    op.drop_index("ix_subscription_changes_effective_at", table_name="subscription_changes")
    op.drop_index("ix_subscription_changes_status", table_name="subscription_changes")
    op.drop_index("ix_subscription_changes_workspace_id", table_name="subscription_changes")
    op.drop_table("subscription_changes")

    op.drop_column("workspace_limits", "currency")
    op.drop_column("workspace_limits", "price_micros")
    op.drop_column("workspace_limits", "support_level")
    op.drop_column("workspace_limits", "max_sources")
    op.drop_column("workspace_limits", "max_monthly_credits")
