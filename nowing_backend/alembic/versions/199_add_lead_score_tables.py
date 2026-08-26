"""add lead score tables

Revision ID: 199
Revises: 198
Create Date: 2026-08-15 00:00:00.000000

"""

from collections.abc import Sequence

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Boolean,
    Column,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "199"
down_revision: str | None = "198"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        Column("icp_criteria", JSONB, nullable=True),
    )

    op.create_table(
        "leads",
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
            primary_key=True,
        ),
        Column("client_id", CITEXT, nullable=True, index=True),
        Column("source", String(100), nullable=False, index=True),
        Column("source_url", Text, nullable=True),
        Column("source_chunk_id", UUID(as_uuid=True), nullable=True, index=True),
        Column("company_name", String(200), nullable=False, index=True),
        Column("domain", String(255), nullable=True, index=True),
        Column("industry", String(100), nullable=True, index=True),
        Column("company_size", String(50), nullable=True),
        Column("location", String(100), nullable=True),
        Column(
            "tech_stack",
            ARRAY(String),
            nullable=True,
            server_default=text("ARRAY[]::varchar[]"),
        ),
        Column("fit_score", Float, nullable=True),
        Column("intent_score", Float, nullable=True),
        Column("composite_score", Float, nullable=True),
        Column(
            "status",
            String(50),
            nullable=False,
            default="new",
            server_default=text("'new'"),
        ),
        Column(
            "enriched",
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
        UniqueConstraint(
            "id",
            name="uq_leads_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "client_id",
            "company_name",
            name="uq_leads_workspace_company",
        ),
    )

    op.create_table(
        "lead_scores",
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
            "lead_id",
            UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        Column(
            "previous_score_id",
            UUID(as_uuid=True),
            ForeignKey("lead_scores.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        Column("company_name", String(200), nullable=False, index=True),
        Column("score", Float, nullable=False),
        Column("fit_score", Float, nullable=False),
        Column("intent_score", Float, nullable=False),
        Column("classification", String(10), nullable=False),
        Column(
            "factors_json",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
        Column("trend", String(10), nullable=True),
        Column("converted_similarity", Float, nullable=True),
        Column(
            "computed_at",
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
        Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_lead_scores_lead_id_workspace_id",
        ),
    )

    op.create_index(
        "ix_lead_scores_workspace_lookup",
        "lead_scores",
        ["workspace_id", "client_id", "lead_id", "computed_at"],
    )

    for table in ("leads", "lead_scores"):
        _create_rls(table)

    # Ensure the declarative model metadata sees the new tables for auto-generation.
    op.get_bind()


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
    for table in ("leads", "lead_scores"):
        _drop_policies(table)


def downgrade() -> None:
    _drop_all_rls()
    op.drop_table("lead_scores")
    op.drop_table("leads")
    op.drop_column("workspaces", "icp_criteria")
