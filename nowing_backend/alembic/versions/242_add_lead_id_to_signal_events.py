"""Add lead_id soft-link to signal_events

Revision ID: 242
Revises: 241
Create Date: 2026-09-23 23:00:00.000000

Story 37.4 review: the Zalo co-pilot joins signals on ``company_name``, so a
company rename drops the lead's signal history and same-name leads share
signals. ``lead_id`` is a plain indexed UUID (not an FK — ``leads`` uses a
composite ``(id, workspace_id)`` primary key, so no single-column FK can
reference it). Populated at write time by ``SignalService._persist_signal``
and backfilled here by exact lower-cased company-name match within the same
workspace; ambiguous same-name leads resolve to the earliest-created lead.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "242"
down_revision: str | None = "241"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE signal_events
            ADD COLUMN IF NOT EXISTS lead_id UUID
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_signal_events_lead_lookup
            ON signal_events (workspace_id, lead_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_signal_events_lead_id
            ON signal_events (lead_id)
        """
    )
    # Backfill: deterministic pick (earliest lead) when a company name maps
    # to multiple leads in one workspace.
    op.execute(
        """
        UPDATE signal_events se
        SET lead_id = sub.id
        FROM (
            SELECT DISTINCT ON (workspace_id, lower(company_name))
                id, workspace_id, lower(company_name) AS cn
            FROM leads
            WHERE company_name IS NOT NULL
            ORDER BY workspace_id, lower(company_name), created_at
        ) sub
        WHERE se.workspace_id = sub.workspace_id
          AND lower(se.company_name) = sub.cn
          AND se.lead_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_signal_events_lead_id")
    op.execute("DROP INDEX IF EXISTS ix_signal_events_lead_lookup")
    op.execute("ALTER TABLE signal_events DROP COLUMN IF EXISTS lead_id")
