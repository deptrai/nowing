"""add workspace_health_daily table (Story 29.2 / AD-52)

Revision ID: d4e7f1a2b5c8
Revises: c2a8e4f9b3d1
Create Date: 2026-09-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e7f1a2b5c8"
down_revision: str | None = "c2a8e4f9b3d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_health_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("active_members_dau", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_members_wau", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_memories", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memory_growth_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recall_queries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remember_queries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("research_queries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_consumed_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_per_turn_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("top_sources", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_coverage_gap_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_members", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "date", name="uq_workspace_health_daily_workspace_date"),
    )
    op.create_index(
        "ix_workspace_health_daily_id", "workspace_health_daily", ["id"]
    )
    op.create_index(
        "ix_workspace_health_daily_workspace_id", "workspace_health_daily", ["workspace_id"]
    )
    op.create_index(
        "ix_workspace_health_daily_date", "workspace_health_daily", ["date"]
    )

    # Row-level security for tenant isolation (INV-29.3)
    op.execute("ALTER TABLE workspace_health_daily ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE workspace_health_daily FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY workspace_health_daily_tenant_read_policy ON workspace_health_daily
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING (workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int);
    """)
    op.execute("""
        CREATE POLICY workspace_health_daily_tenant_write_policy ON workspace_health_daily
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING (workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int)
            WITH CHECK (workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int);
    """)


def _drop_rls_policies() -> None:
    op.execute("DROP POLICY IF EXISTS workspace_health_daily_tenant_read_policy ON workspace_health_daily;")
    op.execute("DROP POLICY IF EXISTS workspace_health_daily_tenant_write_policy ON workspace_health_daily;")
    op.execute("ALTER TABLE workspace_health_daily DISABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    _drop_rls_policies()
    op.drop_index("ix_workspace_health_daily_date", table_name="workspace_health_daily")
    op.drop_index("ix_workspace_health_daily_workspace_id", table_name="workspace_health_daily")
    op.drop_index("ix_workspace_health_daily_id", table_name="workspace_health_daily")
    op.drop_table("workspace_health_daily")
