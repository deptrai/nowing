"""add sequence bounded context tables

Revision ID: 225
Revises: 224
"""

import contextlib
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

try:
    from app.zero_publication import apply_publication
except ImportError:
    apply_publication = None

revision: str = "225"
down_revision: str | None = "224"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def upgrade() -> None:
    # 1. sequences table
    op.create_table(
        "sequences",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("client_id", postgresql.CITEXT(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default=sa.text("'active'"), nullable=False),
        sa.Column("shared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_step_order", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_sequences"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE", name="fk_sequences_workspace_id"),
    )
    op.create_index("ix_sequences_workspace_status", "sequences", ["workspace_id", "status"])
    op.create_index("ix_sequences_workspace_client", "sequences", ["workspace_id", "client_id"])

    # 2. sequence_steps table
    op.create_table(
        "sequence_steps",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("client_id", postgresql.CITEXT(), nullable=True),
        sa.Column("sequence_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(50), server_default=sa.text("'email'"), nullable=False),
        sa.Column("template", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("wait_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("condition_config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_steps"),
        sa.ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_steps_sequence",
        ),
    )
    op.create_index("ix_sequence_steps_order", "sequence_steps", ["workspace_id", "sequence_id", "step_order"])

    # 3. sequence_runs table
    op.create_table(
        "sequence_runs",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("client_id", postgresql.CITEXT(), nullable=True),
        sa.Column("sequence_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "triggering_alert_rule_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("alert_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(50), server_default=sa.text("'running'"), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_runs"),
        sa.ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_runs_sequence",
        ),
    )
    op.create_index("ix_sequence_runs_seq", "sequence_runs", ["workspace_id", "sequence_id", "status"])

    # 4. sequence_enrollments table
    op.create_table(
        "sequence_enrollments",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("client_id", postgresql.CITEXT(), nullable=True),
        sa.Column("sequence_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_run_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("current_step", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.String(50), server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_event_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_enrollments"),
        sa.UniqueConstraint(
            "sequence_id", "lead_id", "workspace_id",
            name="uq_sequence_enrollments_seq_lead",
        ),
        sa.ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_enrollments_sequence",
        ),
        sa.ForeignKeyConstraint(
            ["sequence_run_id", "workspace_id"],
            ["sequence_runs.id", "sequence_runs.workspace_id"],
            ondelete="SET NULL",
            name="fk_sequence_enrollments_run",
        ),
    )
    op.create_index("ix_sequence_enrollments_sched", "sequence_enrollments", ["workspace_id", "status", "scheduled_at"])
    op.create_index("ix_sequence_enrollments_lead", "sequence_enrollments", ["workspace_id", "lead_id"])

    # 5. sequence_events table
    op.create_table(
        "sequence_events",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("client_id", postgresql.CITEXT(), nullable=True),
        sa.Column("enrollment_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_subtype", sa.String(100), nullable=True),
        sa.Column("channel", sa.String(50), server_default=sa.text("'email'"), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("provider_msg_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_events"),
        sa.ForeignKeyConstraint(
            ["enrollment_id", "workspace_id"],
            ["sequence_enrollments.id", "sequence_enrollments.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_events_enrollment",
        ),
        sa.ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_events_sequence",
        ),
    )
    op.create_index("ix_sequence_events_enrollment", "sequence_events", ["workspace_id", "enrollment_id", "event_type"])
    op.create_index("ix_sequence_events_seq_type", "sequence_events", ["workspace_id", "sequence_id", "event_type"])

    # 6. Apply RLS to all 5 tables
    for table in ("sequences", "sequence_steps", "sequence_runs", "sequence_enrollments", "sequence_events"):
        _create_rls(table)

    # 7. Reconcile publication if configured
    if apply_publication:
        with contextlib.suppress(Exception):
            apply_publication(op.get_bind())


def downgrade() -> None:
    for table in ("sequence_events", "sequence_enrollments", "sequence_runs", "sequence_steps", "sequences"):
        _drop_policies(table)
        op.drop_table(table)
