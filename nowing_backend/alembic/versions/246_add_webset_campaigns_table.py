"""Add webset_campaigns table for ChainLens Websets lead tracking (Story 41.1).

Revision ID: 246
Revises: 245
Create Date: 2026-10-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "246"
down_revision: str | None = "245"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webset_campaigns",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("webset_id", sa.String(length=255), nullable=False),
        sa.Column("campaign_id", sa.String(length=255), nullable=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("webhook_secret", sa.String(length=255), nullable=False),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_delivery_id", sa.String(length=255), nullable=True),
        sa.Column(
            "imported_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_webset_campaigns_webset_id",
        "webset_campaigns",
        ["webset_id"],
        unique=True,
    )
    op.create_index(
        "ix_webset_campaigns_workspace_id",
        "webset_campaigns",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_webset_campaigns_campaign_id",
        "webset_campaigns",
        ["campaign_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_webset_campaigns_campaign_id", table_name="webset_campaigns")
    op.drop_index("ix_webset_campaigns_workspace_id", table_name="webset_campaigns")
    op.drop_index("ix_webset_campaigns_webset_id", table_name="webset_campaigns")
    op.drop_table("webset_campaigns")
