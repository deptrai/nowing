"""Add LARK_CALENDAR_CONNECTOR to searchsourceconnectortype

Revision ID: 240
Revises: 239
Create Date: 2026-09-23 00:00:00.000000

Story 37.3 (AC-1): Lark Calendar OAuth credentials are stored as workspace
connectors keyed by this connector type so the meeting booking engine can
resolve them via ``CalendarAvailabilityService.resolve_credentials``.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "240"
down_revision: str | None = "239"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'LARK_CALENDAR_CONNECTOR' to the connector enum if missing."""
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'searchsourceconnectortype' AND e.enumlabel = 'LARK_CALENDAR_CONNECTOR'
        ) THEN
            ALTER TYPE searchsourceconnectortype ADD VALUE 'LARK_CALENDAR_CONNECTOR';
        END IF;
    END
    $$;
    """
    )


def downgrade() -> None:
    """PostgreSQL does not support removing enum values; no-op."""
