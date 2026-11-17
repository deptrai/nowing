"""Add workspace_sip_trunks table for BYO-SIP & Voice Brandname (Story 38.6).

Revision ID: 244
Revises: 243
Create Date: 2026-10-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "244"
down_revision: str | None = "243"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_sip_trunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("brandname", sa.String(length=50), nullable=True),
        sa.Column("outbound_did", sa.String(length=30), nullable=False),
        sa.Column("sip_server", sa.String(length=255), nullable=False),
        sa.Column("sip_username", sa.String(length=100), nullable=False),
        sa.Column("sip_password_encrypted", sa.String(length=512), nullable=False),
        sa.Column("livekit_trunk_id", sa.String(length=100), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_workspace_sip_trunks_workspace_id",
        "workspace_sip_trunks",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_sip_trunks_created_at",
        "workspace_sip_trunks",
        ["created_at"],
    )
    op.create_index(
        "ix_workspace_sip_trunks_ws_active",
        "workspace_sip_trunks",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_workspace_sip_trunks_ws_default",
        "workspace_sip_trunks",
        ["workspace_id", "is_default"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_sip_trunks_ws_default",
        table_name="workspace_sip_trunks",
    )
    op.drop_index(
        "ix_workspace_sip_trunks_ws_active",
        table_name="workspace_sip_trunks",
    )
    op.drop_index(
        "ix_workspace_sip_trunks_created_at",
        table_name="workspace_sip_trunks",
    )
    op.drop_index(
        "ix_workspace_sip_trunks_workspace_id",
        table_name="workspace_sip_trunks",
    )
    op.drop_table("workspace_sip_trunks")
