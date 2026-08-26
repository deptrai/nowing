"""partition leads table zero downtime with 16 hash shards and RLS

Revision ID: 217
Revises: 216
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "217"
down_revision: str | None = "216"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Partitioning of the leads table is deferred.

    The original zero-downtime partition migration was incompatible with the
    subsequent column additions (corporate/Zalo/enrichment columns) and with
    the composite primary key that the rest of the schema now uses.  The table
    remains un-partitioned; RLS is added by earlier migrations and the
    zero_publication reconciliation is left to app.zero_publication.
    """


def downgrade() -> None:
    conn = op.get_bind()

    # Drop composite foreign keys
    composite_fks = [
        ("lead_scores", "fk_lead_scores_lead_id_workspace_id"),
        ("enrichment_requests", "fk_enrichment_requests_lead_id_workspace_id"),
        ("verified_contacts", "fk_verified_contacts_lead_id_workspace_id"),
        ("phone_waterfall_logs", "fk_phone_waterfall_logs_lead_id_workspace_id"),
        ("zalo_message_logs", "fk_zalo_message_logs_lead_id_workspace_id"),
        ("outcome_events", "fk_outcome_events_lead_id_workspace_id"),
    ]
    for table_name, fk_name in composite_fks:
        conn.execute(
            text(
                f"ALTER TABLE IF EXISTS {table_name} DROP CONSTRAINT IF EXISTS {fk_name};"
            )
        )

    # Drop partitioned table
    conn.execute(text("DROP TABLE IF EXISTS leads CASCADE;"))

    # Restore legacy unpartitioned table
    conn.execute(text("ALTER TABLE IF EXISTS leads_legacy_backup RENAME TO leads;"))

    # Restore old foreign keys
    conn.execute(
        text(
            "ALTER TABLE IF EXISTS lead_scores ADD CONSTRAINT lead_scores_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE IF EXISTS enrichment_requests ADD CONSTRAINT enrichment_requests_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE IF EXISTS verified_contacts ADD CONSTRAINT verified_contacts_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE IF EXISTS phone_waterfall_logs ADD CONSTRAINT phone_waterfall_logs_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE IF EXISTS zalo_message_logs ADD CONSTRAINT zalo_message_logs_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE SET NULL;"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE IF EXISTS outcome_events ADD CONSTRAINT outcome_events_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"
        )
    )
