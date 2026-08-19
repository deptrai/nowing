"""add telegram checkpoint messages table

Revision ID: 226
Revises: 225
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "226"
down_revision: str | None = "49988ab02307"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_checkpoint_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("callback_token", sa.String(length=24), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="sent", nullable=False
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_message_id", sa.Text(), nullable=True),
        sa.Column("external_peer_id", sa.Text(), nullable=True),
        sa.Column("unlocked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "action_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["verified_contacts.id"],
            name="fk_telegram_checkpoint_contact_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_telegram_checkpoint_lead_id_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["dsh_missions.id"],
            name="fk_telegram_checkpoint_mission_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_telegram_checkpoint_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_telegram_checkpoint_workspace_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "callback_token", name="uq_telegram_checkpoint_callback_token"
        ),
        sa.CheckConstraint(
            "status IN ('sent', 'unlocked', 'dismissed', 'refunded')",
            name="ck_telegram_checkpoint_status",
        ),
        sa.CheckConstraint(
            "callback_token ~ '^[A-Za-z0-9_-]{16,24}$'",
            name="ck_telegram_checkpoint_callback_token",
        ),
    )
    op.create_index(
        "ix_telegram_checkpoint_message_peer",
        "telegram_checkpoint_messages",
        ["external_message_id", "external_peer_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_checkpoint_workspace_mission",
        "telegram_checkpoint_messages",
        ["workspace_id", "mission_id"],
        unique=True,
        postgresql_where=sa.text("status != 'failed'"),
    )
    op.create_index(
        "ix_telegram_checkpoint_workspace_lead",
        "telegram_checkpoint_messages",
        ["workspace_id", "lead_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_checkpoint_workspace_id",
        "telegram_checkpoint_messages",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_checkpoint_mission_id",
        "telegram_checkpoint_messages",
        ["mission_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_checkpoint_lead_id",
        "telegram_checkpoint_messages",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_checkpoint_contact_id",
        "telegram_checkpoint_messages",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_checkpoint_user_id",
        "telegram_checkpoint_messages",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_checkpoint_messages_created_at",
        "telegram_checkpoint_messages",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("telegram_checkpoint_messages")
