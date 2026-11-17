"""Lead campaign persistence tables (Epic 44.1).

Revision ID: 251
Revises: 250
Create Date: 2026-11-18

- ``lead_campaigns``: chiến dịch bền vững; ``(workspace_id, name, direction)``
  unique — get-or-create race-safe trên ingest path.
- ``campaign_runs``: mỗi lần chạy; chỉ ``campaign_service.open_campaign_run``
  được INSERT (advisory lock + guard running).
- ``campaign_leads``: junction campaign↔lead với composite FK
  ``(lead_id, workspace_id)`` → ``leads(id, workspace_id)``; ``run_id`` ghi
  run đầu tiên attach (ON DELETE SET NULL).

Tenant RLS ENABLE + FORCE trên cả 3 bảng, predicate CHỈ trên
``workspace_id`` (copy inline từ migration 221 — helper không import được).
``campaign_leads`` cố tình KHÔNG có lead-visibility policy (spec 44.1
explicitly: no lead-visibility policy on junction).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "251"
down_revision: str | None = "250"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("lead_campaigns", "campaign_runs", "campaign_leads")


def _workspace_predicate(table: str) -> str:
    # Spec 44.1: predicate CHỈ workspace_id (không client_id, không
    # lead-visibility). Copy pattern từ migration 221 _tenant_predicate.
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
    """


def _create_rls(table: str) -> None:
    predicate = _workspace_predicate(table)
    op.execute(  # nosemgrep
        f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING ({predicate});
    """
    )
    op.execute(  # nosemgrep
        f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({predicate})
            WITH CHECK ({predicate});
    """
    )
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")  # nosemgrep
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")  # nosemgrep


def _drop_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table};")  # nosemgrep
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    op.create_table(
        "lead_campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("input_payload", JSONB, nullable=True),
        sa.Column("schedule_frequency", sa.String(50), nullable=True),
        sa.Column("schedule_cron", sa.String(100), nullable=True),
        sa.Column("max_runs", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="created",
        ),
        sa.Column(
            "skipped_by_quota",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "name",
            "direction",
            name="uq_lead_campaigns_workspace_name_direction",
        ),
    )
    op.create_index(
        "ix_lead_campaigns_workspace_status",
        "lead_campaigns",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_lead_campaigns_workspace_source",
        "lead_campaigns",
        ["workspace_id", "source"],
    )

    op.create_table(
        "campaign_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lead_campaigns.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("spec_snapshot", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", JSONB, nullable=True),
        sa.Column("cost_micros", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_campaign_runs_workspace_campaign_created",
        "campaign_runs",
        ["workspace_id", "campaign_id", "created_at"],
    )

    op.create_table(
        "campaign_leads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lead_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("lead_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_leads"),
        sa.ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_campaign_leads_lead_id_workspace_id",
        ),
        sa.UniqueConstraint(
            "campaign_id", "lead_id", name="uq_campaign_leads_campaign_lead"
        ),
    )
    op.create_index(
        "ix_campaign_leads_campaign", "campaign_leads", ["campaign_id"]
    )
    op.create_index(
        "ix_campaign_leads_lead_workspace",
        "campaign_leads",
        ["lead_id", "workspace_id"],
    )

    for table in _TABLES:
        _create_rls(table)


def downgrade() -> None:
    for table in reversed(_TABLES):
        _drop_rls(table)
    op.drop_table("campaign_leads")
    op.drop_table("campaign_runs")
    op.drop_table("lead_campaigns")
