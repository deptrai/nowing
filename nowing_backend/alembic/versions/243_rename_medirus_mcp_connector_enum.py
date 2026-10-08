"""Rename XACTIONS_MCP_CONNECTOR enum value to MEDIRUS_MCP_CONNECTOR

Revision ID: 243
Revises: 242
Create Date: 2026-10-08 16:30:00.000000

Project rename: XActions -> Medirus. The historical migration
``5bd0001357ae`` was renamed in-place, so fresh databases already get
``MEDIRUS_MCP_CONNECTOR``; the value rename here is therefore guarded —
it only runs when the legacy ``XACTIONS_MCP_CONNECTOR`` label still
exists (databases migrated before the rename). Also updates the seeded
connector display name ``XActions`` -> ``Medirus``.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "243"
down_revision: str | None = "242"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'searchsourceconnectortype'
                  AND e.enumlabel = 'XACTIONS_MCP_CONNECTOR'
            ) THEN
                ALTER TYPE searchsourceconnectortype
                    RENAME VALUE 'XACTIONS_MCP_CONNECTOR' TO 'MEDIRUS_MCP_CONNECTOR';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        UPDATE search_source_connectors
        SET name = 'Medirus'
        WHERE name = 'XActions'
          AND connector_type = 'MEDIRUS_MCP_CONNECTOR';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'searchsourceconnectortype'
                  AND e.enumlabel = 'MEDIRUS_MCP_CONNECTOR'
            ) THEN
                ALTER TYPE searchsourceconnectortype
                    RENAME VALUE 'MEDIRUS_MCP_CONNECTOR' TO 'XACTIONS_MCP_CONNECTOR';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        UPDATE search_source_connectors
        SET name = 'XActions'
        WHERE name = 'Medirus'
          AND connector_type = 'XACTIONS_MCP_CONNECTOR';
        """
    )
