"""Add missing ix_webset_campaigns_created_at index (Epic 41 retro AI-41.8).

Revision ID: 249
Revises: 248
Create Date: 2026-10-11

TimestampMixin declares created_at with index=True (app/db/base.py:38) but the
246 table migration only created the explicit webset_id/workspace_id/campaign_id
indexes — the ORM expects this index to exist.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "249"
down_revision: str | None = "248"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_webset_campaigns_created_at",
        "webset_campaigns",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webset_campaigns_created_at", table_name="webset_campaigns")
