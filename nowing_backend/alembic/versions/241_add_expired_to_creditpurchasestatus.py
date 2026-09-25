"""Add EXPIRED to creditpurchasestatus

Revision ID: 241
Revises: 240
Create Date: 2026-09-23 00:00:01.000000

Story 37.7 (AC-2): VietQR top-up intents expire after a 10-minute transfer
window. ``expired`` is a distinct state from ``failed`` so a late-arriving
Napas bank-transfer webhook can still credit the wallet (the money did
arrive) while ``failed`` stays terminal for real payment failures.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "241"
down_revision: str | None = "240"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'expired' to the creditpurchasestatus enum if missing."""
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'creditpurchasestatus' AND e.enumlabel = 'expired'
        ) THEN
            ALTER TYPE creditpurchasestatus ADD VALUE 'expired';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """PostgreSQL does not support removing enum values; no-op."""
