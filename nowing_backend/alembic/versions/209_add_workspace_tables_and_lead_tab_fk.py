"""Add workspace_tables, export_jobs and lead tab FK (Story 21.13).

Revision ID: 209
Revises: 208
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from alembic import op
from app.zero_publication import apply_publication

revision: str = "209"
down_revision: str | None = "208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_tables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workspace_id",
            Integer,
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", String(200), nullable=False),
        sa.Column("icon", String(50), nullable=False, server_default=sa.text("'table'")),
        sa.Column("filter_preset", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("columns_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_workspace_tables_created_at",
        "workspace_tables",
        ["created_at"],
    )

    op.add_column(
        "leads",
        sa.Column(
            "table_id",
            UUID(as_uuid=True),
            ForeignKey("workspace_tables.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_leads_table_id", "leads", ["table_id"])

    op.create_table(
        "export_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workspace_id",
            Integer,
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "table_id",
            UUID(as_uuid=True),
            ForeignKey("workspace_tables.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("export_type", String(50), nullable=False),
        sa.Column("status", String(50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("total_rows", Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("processed_rows", Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("target_url", Text, nullable=True),
        sa.Column("error_message", Text, nullable=True),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_export_jobs_workspace_lookup",
        "export_jobs",
        ["workspace_id", sa.text("created_at DESC")],
    )

    # Reconcile zero_publication
    bind = op.get_bind()
    apply_publication(bind)


def downgrade() -> None:
    op.drop_index("ix_export_jobs_workspace_lookup", table_name="export_jobs")
    op.drop_table("export_jobs")
    op.drop_index("ix_leads_table_id", table_name="leads")
    op.drop_column("leads", "table_id")
    op.drop_index("ix_workspace_tables_created_at", table_name="workspace_tables")
    op.drop_table("workspace_tables")

    bind = op.get_bind()
    apply_publication(bind)
