"""add inbound email and scheduled dsh missions

Revision ID: 236
Revises: ea7aca64ccff
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "236"
down_revision: Union[str, None] = "ea7aca64ccff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _workspace_predicate(table: str) -> str:
    """Workspace-only read predicate."""
    return f"{table}.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int"


def _drop_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table};")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _create_rls(table: str) -> None:
    _drop_rls(table)
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
            USING ({_workspace_predicate(table)})
            WITH CHECK ({_workspace_predicate(table)});
    """)
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    """Add inbound_email_event table and extend dsh_missions for scheduled reports."""

    # ------------------------------------------------------------------
    # Inbound email event table
    # ------------------------------------------------------------------
    op.create_table(
        "inbound_email_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer,
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("message_id", sa.Text, nullable=True),
        sa.Column("from_address", sa.Text, nullable=False),
        sa.Column("to_address", sa.Text, nullable=False),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("attachments", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="received",
        ),
        sa.Column("dedupe_key", sa.String(64), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'utc')"),
        ),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_inbound_email_event_workspace_id",
        "inbound_email_event",
        ["workspace_id"],
    )
    op.create_index(
        "ix_inbound_email_event_status",
        "inbound_email_event",
        ["status"],
    )
    op.create_unique_constraint(
        "uq_inbound_email_event_provider_message_id",
        "inbound_email_event",
        ["provider", "message_id"],
    )

    _create_rls("inbound_email_event")

    # ------------------------------------------------------------------
    # DshMissions scheduled-mission columns
    # ------------------------------------------------------------------
    op.add_column(
        "dsh_missions",
        sa.Column("schedule", postgresql.JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "dsh_missions",
        sa.Column("source", sa.String(32), nullable=True),
    )
    op.add_column(
        "dsh_missions",
        sa.Column("request_text", sa.Text, nullable=True),
    )
    op.add_column(
        "dsh_missions",
        sa.Column("next_fire_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "dsh_missions",
        sa.Column("last_fired_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_dsh_missions_next_fire_at",
        "dsh_missions",
        ["workspace_id", "status", "next_fire_at"],
    )


def downgrade() -> None:
    """Reverse the schema changes."""
    _drop_rls("inbound_email_event")
    op.drop_constraint(
        "uq_inbound_email_event_provider_message_id",
        "inbound_email_event",
        type_="unique",
    )
    op.drop_table("inbound_email_event")

    op.drop_index("ix_dsh_missions_next_fire_at", table_name="dsh_missions")
    op.drop_column("dsh_missions", "last_fired_at")
    op.drop_column("dsh_missions", "next_fire_at")
    op.drop_column("dsh_missions", "request_text")
    op.drop_column("dsh_missions", "source")
    op.drop_column("dsh_missions", "schedule")
