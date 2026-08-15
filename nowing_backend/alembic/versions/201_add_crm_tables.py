"""add crm tables

Revision ID: 201
Revises: 199
Create Date: 2026-08-15 00:00:00.000000

"""

from collections.abc import Sequence

from sqlalchemy import (
    TIMESTAMP,
    Column,
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
revision: str = "201"
down_revision: str | None = "199"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_connections",
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
        Column("provider", String(50), nullable=False, index=True),
        Column(
            "status",
            String(20),
            nullable=False,
            server_default=text("'pending'"),
        ),
        Column("credentials_encrypted", Text, nullable=False),
        Column(
            "sync_config",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
        Column("last_sync_at", TIMESTAMP(timezone=True), nullable=True),
        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        UniqueConstraint(
            "workspace_id",
            "client_id",
            "provider",
            name="uq_crm_connections_workspace_client_provider",
        ),
    )

    op.create_index(
        "ix_crm_connections_workspace_lookup",
        "crm_connections",
        ["workspace_id", "client_id", "provider", "status"],
    )

    op.create_table(
        "crm_sync_logs",
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
            "connection_id",
            UUID(as_uuid=True),
            ForeignKey("crm_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("direction", String(20), nullable=False),
        Column("entity_type", String(50), nullable=False),
        Column("entity_id", UUID(as_uuid=True), nullable=False, index=True),
        Column("status", String(20), nullable=False),
        Column("error_message", Text, nullable=True),
        Column(
            "synced_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )

    op.create_index(
        "ix_crm_sync_logs_workspace_lookup",
        "crm_sync_logs",
        ["workspace_id", "client_id", "connection_id", "synced_at"],
    )

    for table in ("crm_connections", "crm_sync_logs"):
        _create_rls(table)

    op.execute("""
        ALTER TYPE memory_source_type ADD VALUE IF NOT EXISTS 'crm_connection';
    """)
    op.execute("""
        ALTER TYPE memory_source_type ADD VALUE IF NOT EXISTS 'crm_sync';
    """)


def _workspace_predicate(table: str) -> str:
    return f"{table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int"


def _tenant_predicate(table: str) -> str:
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
        AND {table}.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
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
            USING ({predicate});
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
    for table in ("crm_connections", "crm_sync_logs"):
        _drop_policies(table)


def downgrade() -> None:
    _drop_all_rls()
    op.drop_table("crm_sync_logs")
    op.drop_table("crm_connections")
