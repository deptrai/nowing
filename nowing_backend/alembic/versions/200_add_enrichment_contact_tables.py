"""add enrichment and verified contact tables

Revision ID: 200
Revises: 199
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
    ForeignKeyConstraint,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "200"
down_revision: str | None = "199"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enrichment_requests",
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
            nullable=False,
            index=True,
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_enrichment_requests_lead_id_workspace_id",
        ),
        Column(
            "status",
            String(20),
            nullable=False,
            default="pending",
            server_default=text("'pending'"),
        ),
        Column(
            "provider_results",
            JSONB,
            nullable=True,
            server_default=text("'{}'::jsonb"),
        ),
        Column(
            "cost_micros",
            BigInteger,
            nullable=False,
            default=0,
            server_default=text("0"),
        ),
        Column(
            "contact_count",
            Integer,
            nullable=False,
            default=0,
            server_default=text("0"),
        ),
        Column(
            "requested_count",
            Integer,
            nullable=False,
            default=5,
            server_default=text("5"),
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

    op.create_table(
        "verified_contacts",
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
            nullable=False,
            index=True,
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_verified_contacts_lead_id_workspace_id",
        ),
        Column(
            "enrichment_request_id",
            UUID(as_uuid=True),
            ForeignKey("enrichment_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("name", String(200), nullable=True),
        Column("title", String(200), nullable=True),
        Column("email", CITEXT, nullable=False, index=True),
        Column("phone", String(200), nullable=True),
        Column(
            "verification_status",
            String(20),
            nullable=False,
            default="unverified",
            server_default=text("'unverified'"),
        ),
        Column(
            "confidence",
            Float,
            nullable=False,
            default=0.0,
            server_default=text("0"),
        ),
        Column(
            "source_provider",
            String(20),
            nullable=False,
            default="fallback",
            server_default=text("'fallback'"),
        ),
        Column(
            "consent",
            Boolean,
            nullable=False,
            default=False,
            server_default=text("false"),
        ),
        Column("consent_status", String(50), nullable=True),
        Column("legal_basis", String(50), nullable=True),
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

    for table in ("enrichment_requests", "verified_contacts"):
        _create_rls(table)

    op.create_index(
        "ix_enrichment_requests_tenant_lookup",
        "enrichment_requests",
        ["workspace_id", "client_id", "lead_id", text("created_at DESC")],
    )
    op.create_index(
        "ix_verified_contacts_tenant_lookup",
        "verified_contacts",
        ["workspace_id", "client_id", "lead_id", text("created_at DESC")],
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
    # FORCE so the application role (table owner) cannot bypass tenant isolation.
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def _drop_all_rls() -> None:
    for table in ("enrichment_requests", "verified_contacts"):
        _drop_policies(table)


def downgrade() -> None:
    _drop_all_rls()
    # CASCADE removes dependent foreign key constraints added by later migrations
    # (e.g. phone_waterfall_logs, telegram_checkpoint_messages) without dropping
    # the referencing tables themselves.
    op.execute("DROP TABLE IF EXISTS verified_contacts CASCADE;")
    op.execute("DROP TABLE IF EXISTS enrichment_requests CASCADE;")