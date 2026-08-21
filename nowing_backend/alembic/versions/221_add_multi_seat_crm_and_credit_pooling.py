"""add multi seat crm pipeline and shared workspace credit pooling

Revision ID: 221
Revises: 218
Create Date: 2026-08-16 00:00:00.000000

"""

import contextlib
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID

from alembic import op
from app.zero_publication import apply_publication

# revision identifiers, used by Alembic.
revision: str = "221"
down_revision: str | None = "220"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add credit_micros_balance to workspaces
    op.add_column(
        "workspaces",
        sa.Column(
            "credit_micros_balance",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )

    # 2. Add spend cap and lead distribution fields to workspace_memberships
    op.add_column(
        "workspace_memberships",
        sa.Column(
            "monthly_spend_cap_micros",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "workspace_memberships",
        sa.Column(
            "monthly_spent_micros",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "workspace_memberships",
        sa.Column(
            "is_accepting_leads",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "workspace_memberships",
        sa.Column(
            "lead_capacity",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
    )
    op.add_column(
        "workspace_memberships",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="ACTIVE",
        ),
    )

    # 3. Add CRM pipeline & OCC columns to leads (and leads_partitioned if present)
    # Check if leads table / partition exists and add columns
    for table_name in ("leads", "leads_partitioned"):
        has_table = conn.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = :t"),
            {"t": table_name},
        ).scalar()
        if has_table:
            # Idempotent raw DDL: column/index additions use IF NOT EXISTS guards.
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS stage_id UUID;"))
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS assigned_to_user_id UUID REFERENCES \"user\"(id) ON DELETE SET NULL;"))
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_assigned_to_user_id ON {table_name} (assigned_to_user_id);"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_stage_id ON {table_name} (stage_id);"))

    # 4. Create lead_pipeline_stages table (Composite PK (id, workspace_id))
    op.create_table(
        "lead_pipeline_stages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
            index=True,
        ),
        sa.Column("client_id", CITEXT, nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("color", sa.String(30), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_lead_pipeline_stages"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_lead_pipeline_stages_workspace_slug"),
    )
    op.create_index(
        "ix_lead_pipeline_stages_workspace_pos",
        "lead_pipeline_stages",
        ["workspace_id", "position"],
    )

    # 5. Create lead_assignments table (Composite PK (id, workspace_id))
    op.create_table(
        "lead_assignments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
            index=True,
        ),
        sa.Column("client_id", CITEXT, nullable=True, index=True),
        sa.Column("lead_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "assigned_to_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "assigned_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_by", sa.String(50), nullable=False, server_default="auto_round_robin"),
        sa.Column("status", sa.String(30), nullable=False, server_default="assigned"),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_lead_assignments"),
        sa.ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_lead_assignments_lead_id_workspace_id",
        ),
    )
    op.create_index(
        "ix_lead_assignments_lookup",
        "lead_assignments",
        ["workspace_id", "lead_id", "created_at"],
    )
    op.create_index(
        "ix_lead_assignments_user",
        "lead_assignments",
        ["workspace_id", "assigned_to_user_id", "status"],
    )

    # 6. Create lead_activity_logs table (Composite PK (id, workspace_id))
    op.create_table(
        "lead_activity_logs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
            index=True,
        ),
        sa.Column("client_id", CITEXT, nullable=True, index=True),
        sa.Column("lead_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("details", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_lead_activity_logs"),
        sa.ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_lead_activity_logs_lead_id_workspace_id",
        ),
    )
    op.create_index(
        "ix_lead_activity_logs_timeline",
        "lead_activity_logs",
        ["workspace_id", "lead_id", "created_at"],
    )

    # 7. Apply RLS to new CRM tables and strengthen leads visibility
    _create_lead_rls("leads")
    _create_lead_assignment_rls("lead_assignments")
    _create_lead_activity_log_rls("lead_activity_logs")
    _create_rls("lead_pipeline_stages")

    # 8. Reconcile zero publication
    with contextlib.suppress(Exception):
        apply_publication(op.get_bind())


def _tenant_predicate(table: str) -> str:
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
        AND {table}.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
    """


def _is_lead_admin_expr() -> str:
    """GUC expression: 'true' when the caller is a workspace lead admin."""
    return "COALESCE(NULLIF(current_setting('app.is_lead_admin', true), ''), 'false') = 'true'"


def _current_user_id_expr() -> str:
    """GUC expression returning the calling user's UUID or NULL."""
    return "NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def _lead_visibility_predicate(table: str) -> str:
    """Tenant predicate plus lead-assignment visibility for leads/lead_assignments."""
    tenant = _tenant_predicate(table)
    admin = _is_lead_admin_expr()
    user_id = _current_user_id_expr()
    return f"""
        {tenant}
        AND (
            {admin}
            OR {table}.assigned_to_user_id IS NOT DISTINCT FROM {user_id}
        )
    """


def _lead_activity_log_visibility_predicate(table: str) -> str:
    """Tenant predicate plus visibility only if the related lead is visible."""
    tenant = _tenant_predicate(table)
    admin = _is_lead_admin_expr()
    user_id = _current_user_id_expr()
    return f"""
        {tenant}
        AND (
            {admin}
            OR EXISTS (
                SELECT 1 FROM leads
                WHERE leads.id = {table}.lead_id
                  AND leads.workspace_id = {table}.workspace_id
                  AND leads.assigned_to_user_id IS NOT DISTINCT FROM {user_id}
            )
        )
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
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def _create_lead_rls(table: str) -> None:
    """Workspace/client tenant RLS with role/assignment lead visibility."""
    _drop_policies(table)
    predicate = _lead_visibility_predicate(table)
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
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def _create_lead_assignment_rls(table: str) -> None:
    """Lead assignments inherit the same visibility as leads."""
    _create_lead_rls(table)


def _create_lead_activity_log_rls(table: str) -> None:
    """Activity logs visible only for visible leads."""
    _drop_policies(table)
    predicate = _lead_activity_log_visibility_predicate(table)
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
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def _create_legacy_lead_rls(table: str) -> None:
    """Workspace-only RLS used during downgrade."""
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
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    # Revert leads to workspace-only RLS first.
    _drop_policies("leads")
    _create_legacy_lead_rls("leads")

    for table in ("lead_activity_logs", "lead_assignments", "lead_pipeline_stages"):
        _drop_policies(table)
        op.drop_table(table)

    for table_name in ("leads", "leads_partitioned"):
        try:
            op.execute(text(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS version;"))
            op.execute(text(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS assigned_to_user_id;"))
            op.execute(text(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS stage_id;"))
        except Exception:
            pass

    op.drop_column("workspace_memberships", "status")
    op.drop_column("workspace_memberships", "lead_capacity")
    op.drop_column("workspace_memberships", "is_accepting_leads")
    op.drop_column("workspace_memberships", "monthly_spent_micros")
    op.drop_column("workspace_memberships", "monthly_spend_cap_micros")
    op.drop_column("workspaces", "credit_micros_balance")
