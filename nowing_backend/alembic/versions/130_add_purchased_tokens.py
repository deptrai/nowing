"""130_add_purchased_tokens

Revision ID: 130
Revises: 129
Create Date: 2026-04-15

Adds purchased_tokens and fulfilled_topup_sessions columns to the user table
for tracking PAYG token top-up balance and webhook idempotency.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "130"
down_revision: str | None = "129"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS purchased_tokens INTEGER NOT NULL DEFAULT 0'
    ))
    conn.execute(sa.text(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS fulfilled_topup_sessions TEXT'
    ))


def downgrade() -> None:
    op.drop_column("user", "fulfilled_topup_sessions")
    op.drop_column("user", "purchased_tokens")
