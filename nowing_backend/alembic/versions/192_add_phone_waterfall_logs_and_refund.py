"""add phone_waterfall_logs and refund tracking (Story 21.3 / AD-36 / AD-42)

Revision ID: 192_phone_waterfall
Revises: 211
Create Date: 2026-08-15 00:00:00.000000

"""

from collections.abc import Sequence

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
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
revision: str = "192_phone_waterfall"
down_revision: str | None = "211"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create phone_waterfall_logs table
    op.create_table(
        "phone_waterfall_logs",
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
            "client_id",
            CITEXT,
            ForeignKey("vertical_clients.client_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        Column(
            "lead_id",
            UUID(as_uuid=True),
            ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "contact_id",
            UUID(as_uuid=True),
            ForeignKey("verified_contacts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        Column(
            "tier_reached",
            Integer,
            nullable=False,
            default=1,
            server_default=text("1"),
        ),
        Column(
            "provider_used",
            String(50),
            nullable=False,
            default="unknown",
            server_default=text("'unknown'"),
        ),
        Column(
            "status",
            String(20),
            nullable=False,
            default="pending",
            server_default=text("'pending'"),
        ),
        Column(
            "cost_micros",
            BigInteger,
            nullable=False,
            default=0,
            server_default=text("0"),
        ),
        Column(
            "phone_hash",
            String(64),
            nullable=True,
            index=True,
        ),
        Column(
            "phone_masked",
            String(50),
            nullable=True,
        ),
        Column(
            "raw_response",
            JSONB,
            nullable=True,
            server_default=text("'{}'::jsonb"),
        ),
        Column(
            "refunded_at",
            TIMESTAMP(timezone=True),
            nullable=True,
        ),
        Column(
            "refund_reason",
            String(255),
            nullable=True,
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

    _create_rls("phone_waterfall_logs")

    op.create_index(
        "ix_phone_waterfall_logs_tenant_lookup",
        "phone_waterfall_logs",
        ["workspace_id", "client_id", "lead_id", text("created_at DESC")],
    )

    # 2. Add refund & validity columns to verified_contacts
    op.add_column(
        "verified_contacts",
        Column(
            "is_valid",
            Boolean,
            nullable=False,
            default=True,
            server_default=text("true"),
        ),
    )
    op.add_column(
        "verified_contacts",
        Column(
            "refunded_at",
            TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "verified_contacts",
        Column(
            "invalid_reason",
            String(255),
            nullable=True,
        ),
    )

    # 3. Relax enrichment_request_id and email to nullable in verified_contacts
    op.alter_column(
        "verified_contacts",
        "enrichment_request_id",
        nullable=True,
    )
    op.alter_column(
        "verified_contacts",
        "email",
        nullable=True,
    )


def _workspace_predicate(table: str) -> str:
    return (
        f"{table}.workspace_id IS NOT DISTINCT FROM "
        f"NULLIF(current_setting('app.workspace_id', true), '')::int"
    )


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
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.alter_column("verified_contacts", "email", nullable=False)
    op.alter_column("verified_contacts", "enrichment_request_id", nullable=False)
    op.drop_column("verified_contacts", "invalid_reason")
    op.drop_column("verified_contacts", "refunded_at")
    op.drop_column("verified_contacts", "is_valid")

    _drop_policies("phone_waterfall_logs")
    op.drop_index(
        "ix_phone_waterfall_logs_tenant_lookup", table_name="phone_waterfall_logs"
    )
    op.drop_table("phone_waterfall_logs")
