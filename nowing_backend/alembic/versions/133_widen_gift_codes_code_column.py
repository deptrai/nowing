"""133_widen_gift_codes_code_column

Revision ID: 133
Revises: 132
Create Date: 2026-04-17

Widens gift_codes.code column from VARCHAR(16) to VARCHAR(32) to accommodate
the generated code format `GIFT-XXXX-XXXX-XXXX` (19 characters) from the
webhook fulfillment handler added in Story 6.3. The original migration 132
used VARCHAR(16) which is too narrow for this format.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "133"
down_revision: str | None = "132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen gift_codes.code to VARCHAR(32)."""
    op.alter_column(
        "gift_codes",
        "code",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Refuse to narrow gift_codes.code back to VARCHAR(16).

    The code format `GIFT-XXXX-XXXX-XXXX` is 19 chars and any active rows
    would be silently truncated / fail. Explicit manual intervention is
    required to downgrade safely (either TRUNCATE or shorten the format).
    """
    raise NotImplementedError(
        "Downgrade would truncate gift code values. "
        "Manually delete/rewrite rows before reverting this migration."
    )
