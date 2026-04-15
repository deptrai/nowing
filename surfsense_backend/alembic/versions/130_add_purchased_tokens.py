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
    op.add_column(
        "user",
        sa.Column("purchased_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user",
        sa.Column("fulfilled_topup_sessions", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "fulfilled_topup_sessions")
    op.drop_column("user", "purchased_tokens")
