"""Add soft run provenance to memories + durable run extraction state.

Story 3.13 (FR-40, first-run value — research run produces memory):

* ``memories.source_run_id`` — nullable, indexed PostgreSQL UUID holding the
  ``runs.id`` a scraper-run-derived memory came from. **Deliberately not a
  foreign key** (AC-7): ``runs`` is retained ~30 days and cleaned up
  opportunistically while the memory it produced is durable, so a hard FK would
  either cascade the memory away with its run log or block the cleanup.
  ``memories.source_id`` stays ``INTEGER`` (chat message ids) — the run's UUID
  is *not* coerced into it.
* ``runs.memory_extraction_status`` / ``memory_extraction_completed_at`` /
  ``memory_extraction_skip_reason`` — durable terminal state for the background
  extraction (AC-6). Celery delivery is at-least-once, so "did this run produce
  memory rows" cannot be the only idempotency key: a successful extraction that
  found zero qualifying facts must also be terminal, or every redelivery
  re-calls (and re-pays for) the extraction LLM. ``status`` is indexed because
  the claim is a compare-and-set on it.

Revision ID: 182
Revises: 180

Revision choice: ``180`` is the tracked integration head at baseline
``25ba542c2``. Revision ``181`` is deliberately skipped — Story 3.14 holds an
untracked ``181_add_memories_thread_recency_index.py`` in another working tree,
and reusing the id would collide on merge. If 3.14's ``181`` reaches the
integration branch first, rebase this revision's ``down_revision`` onto it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "182"
down_revision: str | None = "180"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Use the names SQLAlchemy's create_all generates (no naming convention is
# configured on the metadata) so a create_all-bootstrapped DB and a
# migration-upgraded DB carry identical index names.
MEMORY_SOURCE_RUN_INDEX = "ix_memories_source_run_id"
RUN_EXTRACTION_STATUS_INDEX = "ix_runs_memory_extraction_status"


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(MEMORY_SOURCE_RUN_INDEX, "memories", ["source_run_id"])

    op.add_column(
        "runs",
        sa.Column("memory_extraction_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column(
            "memory_extraction_completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "runs",
        sa.Column("memory_extraction_skip_reason", sa.String(length=64), nullable=True),
    )
    op.create_index(RUN_EXTRACTION_STATUS_INDEX, "runs", ["memory_extraction_status"])


def downgrade() -> None:
    op.drop_index(RUN_EXTRACTION_STATUS_INDEX, table_name="runs")
    op.drop_column("runs", "memory_extraction_skip_reason")
    op.drop_column("runs", "memory_extraction_completed_at")
    op.drop_column("runs", "memory_extraction_status")

    op.drop_index(MEMORY_SOURCE_RUN_INDEX, table_name="memories")
    op.drop_column("memories", "source_run_id")
