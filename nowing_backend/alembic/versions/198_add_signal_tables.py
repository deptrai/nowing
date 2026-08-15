"""add signal tables

Revision ID: 198
Revises: 197
Create Date: 2026-08-15 00:00:00.000000

"""

from collections.abc import Sequence

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "198"
down_revision: str | None = "190_add_alert_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "signal_events",
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
        Column("company_name", String(200), nullable=False, index=True),
        Column("signal_type", String(50), nullable=False, index=True),
        Column("source_url", Text, nullable=True),
        Column("chunk_id", UUID(as_uuid=True), nullable=True, index=True),
        Column(
            "confidence",
            Float,
            nullable=False,
            default=0.0,
            server_default=text("0"),
        ),
        Column("detected_at", TIMESTAMP(timezone=True), nullable=False, index=True),
        Column(
            "processed",
            Boolean,
            nullable=False,
            default=False,
            server_default=text("false"),
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
        UniqueConstraint(
            "workspace_id",
            "client_id",
            "company_name",
            "signal_type",
            "source_url",
            "detected_at",
            name="uq_signal_events_unique_signal",
        ),
    )

    op.create_index(
        "ix_signal_events_workspace_lookup",
        "signal_events",
        ["workspace_id", "client_id", "company_name", "signal_type", "detected_at"],
    )

    op.create_table(
        "signal_subscriptions",
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
        Column(
            "signal_types",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
        Column(
            "notification_channels",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
        Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
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
        UniqueConstraint("workspace_id", name="uq_signal_subscriptions_workspace"),
    )

    op.create_table(
        "billing_events",
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
        Column(
            "user_id",
            UUID(as_uuid=True),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        Column("event_entity_type", String(50), nullable=False, index=True),
        Column("event_type", String(50), nullable=False, index=True),
        Column("event_id", UUID(as_uuid=True), nullable=False),
        Column(
            "cost_micros",
            BigInteger,
            nullable=False,
            default=0,
            server_default=text("0"),
        ),
        Column(
            "currency",
            String(3),
            nullable=False,
            server_default=text("'USD'"),
        ),
        Column(
            "cost_basis",
            String(20),
            nullable=False,
            server_default=text("'estimated'"),
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
        "ix_billing_events_event_lookup",
        "billing_events",
        ["event_entity_type", "event_type", "event_id"],
    )

    op.create_index(
        "ix_billing_events_signal_unique",
        "billing_events",
        ["event_id"],
        unique=True,
        postgresql_where="event_entity_type = 'signal_event' AND event_type = 'signal_scan'",
    )

    op.create_index(
        "ix_billing_events_outcome_unique",
        "billing_events",
        ["event_id"],
        unique=True,
        postgresql_where="event_entity_type = 'outcome_event' AND event_type = 'outcome'",
    )

    for table in ("signal_events", "signal_subscriptions", "billing_events"):
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
    predicate = _tenant_predicate(table)
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
    for table in ("signal_events", "signal_subscriptions", "billing_events"):
        _drop_policies(table)


def downgrade() -> None:
    _drop_all_rls()
    op.drop_table("billing_events")
    op.drop_table("signal_subscriptions")
    op.drop_table("signal_events")
