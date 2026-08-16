"""add outcome pricing and promo codes

Revision ID: 216
Revises: 215
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
        sa.Column("pricing_model", sa.String(50), nullable=False, server_default="pay_as_you_go"),
        sa.Column("credit_micros_charged", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("credit_micros_saved", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="VND"),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            index=True,
        ),
    )

    # 2. Create promo_codes table
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("bonus_credit_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("current_uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 3. Create promo_code_claims table (idempotency & per-user claim tracking)
    op.create_table(
        "promo_code_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "promo_code_id",
            sa.Integer(),
            sa.ForeignKey("promo_codes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("credit_micros_awarded", sa.BigInteger(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("promo_code_id", "user_id", name="uq_promo_code_user_claim"),
    )

    # 4. Add pricing plan columns to workspaces table
    op.add_column(
        "workspaces",
        sa.Column(
            "pricing_plan",
            sa.String(50),
            nullable=False,
            server_default="pay_as_you_go",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "monthly_lead_quota",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "leads_used_this_month",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # 5. Enable RLS and Tenant Isolation on outcome_events
    op.execute(sa.text("ALTER TABLE outcome_events ENABLE ROW LEVEL SECURITY;"))
    op.execute(
        sa.text(
            """
            CREATE POLICY outcome_events_workspace_isolation ON outcome_events
            USING (
                workspace_id = NULLIF(current_setting('app.current_workspace_id', true), '')::integer
                OR client_id = NULLIF(current_setting('app.current_client_id', true), '')::citext
                OR current_setting('app.is_admin', true) = 'true'
            );
            """
        )
    )

    # 6. Seed default welcome bonus promo codes (e.g. WELCOME50, ORIGAMIVN)
    op.execute(
        sa.text(
            """
            INSERT INTO promo_codes (code, bonus_credit_micros, max_uses, current_uses, is_active)
            VALUES 
                ('WELCOME50', 50000000, 1000, 0, true),
                ('ORIGAMIVN', 100000000, 500, 0, true),
                ('BDSNOWING', 50000000, 500, 0, true)
            ON CONFLICT (code) DO NOTHING;
            """
        )
    )

    # 7. Add outcome_events and promo_codes to zero publication if exists
    conn = op.get_bind()
    has_pub = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = 'zero_publication'")
    ).scalar()
    if has_pub:
        op.execute(
            sa.text(
                "ALTER PUBLICATION zero_publication ADD TABLE outcome_events, promo_codes, promo_code_claims;"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    has_pub = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = 'zero_publication'")
    ).scalar()
    if has_pub:
        op.execute(
            sa.text(
                "ALTER PUBLICATION zero_publication DROP TABLE IF EXISTS outcome_events, promo_codes, promo_code_claims;"
            )
        )

    op.execute(sa.text("DROP POLICY IF EXISTS outcome_events_workspace_isolation ON outcome_events;"))
    op.drop_column("workspaces", "leads_used_this_month")
    op.drop_column("workspaces", "monthly_lead_quota")
    op.drop_column("workspaces", "pricing_plan")
    op.drop_table("promo_code_claims")
    op.drop_table("promo_codes")
    op.drop_table("outcome_events")
