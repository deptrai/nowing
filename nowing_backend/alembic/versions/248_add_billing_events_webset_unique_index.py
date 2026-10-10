"""Add partial unique index on billing_events.event_id for webset imports (Epic 41 retro AI-41.6).

Revision ID: 248
Revises: 247
Create Date: 2026-10-11

The webset import dedup path does SELECT-then-INSERT on (event_entity_type='webset',
event_type='lead_import', event_id). Without a unique constraint two concurrent
importers could insert the same event_id and double-debit the reservation.
Mirrors the existing ix_billing_events_outcome_unique partial index.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "248"
down_revision: str | None = "247"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_billing_events_webset_event_unique",
        "billing_events",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("event_entity_type = 'webset'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_events_webset_event_unique",
        table_name="billing_events",
        postgresql_where=sa.text("event_entity_type = 'webset'"),
    )
