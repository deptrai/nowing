"""Add RSS feed connector types to SearchSourceConnectorType and DocumentType enums.

Revision ID: 195
Revises: 194

This migration adds the RSS feed connector enum values to both:
- searchsourceconnectortype (for connector type tracking)
- documenttype (for news article document type tracking)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "195"
down_revision: str | None = "194"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONNECTOR_ENUM = "searchsourceconnectortype"
CONNECTOR_NEW_VALUES = ["RSS_FEED"]
DOCUMENT_ENUM = "documenttype"
DOCUMENT_NEW_VALUES = ["NEWS_CONNECTOR"]


def _add_enum_values(enum_name: str, values: list[str]) -> None:
    """Safely add values to an existing PostgreSQL enum type."""
    for value in values:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = '{enum_name}' AND e.enumlabel = '{value}'
                ) THEN
                    ALTER TYPE {enum_name} ADD VALUE '{value}';
                END IF;
            END$$;
            """
        )


def upgrade() -> None:
    """Upgrade schema - add RSS feed connector types to connector and document enums."""
    _add_enum_values(CONNECTOR_ENUM, CONNECTOR_NEW_VALUES)
    _add_enum_values(DOCUMENT_ENUM, DOCUMENT_NEW_VALUES)


def downgrade() -> None:
    """Downgrade schema - removing enum values is complex and left as no-op."""
    pass
