"""add alert tables

Revision ID: 190_add_alert_tables
Revises: ea7aca64ccff
Create Date: 2026-08-13 14:30:00.000000

"""

from collections.abc import Sequence

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "190_add_alert_tables"
down_revision: str | None = "ea7aca64ccff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "alert_rules",
        Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        Column(
            "workspace_id",
            Integer,
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("client_id", CITEXT, nullable=True, index=True),
        Column("capability_id", String(200), nullable=False, index=True),
        Column("name", String(200), nullable=False),
        Column("query", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column("schedule", String(20), nullable=False, server_default=text("'none'")),
        Column("timezone", String(64), nullable=False, server_default=text("'UTC'")),
        Column("cron", String(64), nullable=True),
        Column("next_fire_at", TIMESTAMP(timezone=True), nullable=True, index=True),
        Column("last_fired_at", TIMESTAMP(timezone=True), nullable=True),
        Column(
            "diff_strategy",
            String(40),
            nullable=False,
            server_default=text("'new_items'"),
        ),
        Column("threshold", JSONB, nullable=True),
        Column(
            "target_sequence_id",
            UUID(as_uuid=True),
            nullable=True,
            index=True,
        ),
        Column(
            "target_step_id",
            UUID(as_uuid=True),
            nullable=True,
            index=True,
        ),
        Column(
            "notification_channels",
            JSONB,
            nullable=False,
            server_default=text("'[\"in_app\"]'::jsonb"),
        ),
        Column(
            "enabled",
            Boolean,
            nullable=False,
            default=True,
            server_default=text("true"),
        ),
        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            default=TIMESTAMP,
            server_default=text("now()"),
        ),
        Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            default=TIMESTAMP,
            server_default=text("now()"),
        ),
    )

    op.create_table(
        "alert_snapshots",
        Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        Column(
            "alert_rule_id",
            UUID(as_uuid=True),
            ForeignKey("alert_rules.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "snapshot_json",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
        Column("run_status", String(40), nullable=False),
        Column("degradation_reasons", JSONB, nullable=True),
        Column(
            "new_items_count",
            Integer,
            nullable=False,
            default=0,
            server_default=text("0"),
        ),
        Column(
            "changed_items_count",
            Integer,
            nullable=False,
            default=0,
            server_default=text("0"),
        ),
        Column(
            "removed_items_count",
            Integer,
            nullable=False,
            default=0,
            server_default=text("0"),
        ),
        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )

    op.create_table(
        "alert_subscriptions",
        Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        Column(
            "workspace_id",
            Integer,
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "user_id",
            UUID(as_uuid=True),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "alert_rule_id",
            UUID(as_uuid=True),
            ForeignKey("alert_rules.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "channels",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
        Column(
            "enabled",
            Boolean,
            nullable=False,
            default=True,
            server_default=text("true"),
        ),
        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )

    op.create_index(
        "ix_alert_rules_due",
        "alert_rules",
        ["workspace_id", "enabled", "next_fire_at"],
        postgresql_where="enabled",
    )
    op.create_unique_constraint(
        "uq_alert_subscription_user_rule",
        "alert_subscriptions",
        ["user_id", "alert_rule_id"],
    )

    # Workspace/client RLS for alert data.
    for table in ("alert_rules", "alert_snapshots", "alert_subscriptions"):
        _create_rls(table)


def _workspace_predicate(table: str) -> str:
    return f"{table}.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int"


def _tenant_predicate(table: str) -> str:
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int
        AND {table}.client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)
    """


def _drop_policies(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table};")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _create_rls(table: str) -> None:
    _drop_policies(table)
    # alert_snapshots and alert_subscriptions have no client_id column.
    predicate = (
        _workspace_predicate(table)
        if table in ("alert_snapshots", "alert_subscriptions")
        else _tenant_predicate(table)
    )
    op.execute(f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING ({_workspace_predicate(table)});
    """)
    op.execute(f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({predicate})
            WITH CHECK ({predicate});
    """)
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def _drop_all_rls() -> None:
    for table in ("alert_rules", "alert_snapshots", "alert_subscriptions"):
        _drop_policies(table)


def downgrade() -> None:
    _drop_all_rls()
    op.drop_table("alert_subscriptions")
    op.drop_table("alert_snapshots")
    op.drop_table("alert_rules")
