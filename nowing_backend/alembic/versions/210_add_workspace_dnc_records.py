"""Add workspace_dnc_records table for compliance & opt-out management (Story 21.14).

Revision ID: 210
Revises: 209
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "214_dnc"
down_revision: str | None = "214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_dnc_records",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            Integer,
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "record_type",
            String(20),
            nullable=False,
        ),
        sa.Column(
            "value",
            String(255),
            nullable=True,
        ),
        sa.Column(
            "value_hmac",
            String(64),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reason",
            String(255),
            nullable=True,
            server_default="Opt-out requested",
        ),
        sa.Column(
            "source",
            String(50),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "record_type",
            "value_hmac",
            name="uq_workspace_dnc_entry",
        ),
    )


def downgrade() -> None:
    op.drop_table("workspace_dnc_records")
