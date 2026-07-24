"""Add automation_runs.research_thread_id + 'memory_change' trigger type.

Story 6.5 (FR-35, Memory-Driven Automations):

* Links an automation run to the research thread that drove it — a
  ``continue_research`` step or a research-driven ``memory_change`` trigger
  (AC-4). Nullable FK -> ``research_threads`` with ``ON DELETE SET NULL`` so
  deleting a thread preserves its historical runs.
* Adds ``memory_change`` to the ``automation_trigger_type`` enum so a
  memory-change trigger can be persisted (AC-2), mirroring the safe pattern of
  migration 147 (``event``).

Revision ID: 180
Revises: 179
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "180"
down_revision: str | None = "179"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAME = "automation_trigger_type"
NEW_TRIGGER_VALUE = "memory_change"

# Use the same names SQLAlchemy's create_all generates (no naming convention is
# configured on the metadata), so a create_all-bootstrapped DB and a
# migration-upgraded DB carry identical constraint/index names.
FK_NAME = "automation_runs_research_thread_id_fkey"
INDEX_NAME = "ix_automation_runs_research_thread_id"


def upgrade() -> None:
    # Safely add 'memory_change' to the trigger-type enum if missing
    # (mirrors migration 147; the new value is not used in this transaction).
    op.execute(
        f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = '{ENUM_NAME}' AND e.enumlabel = '{NEW_TRIGGER_VALUE}'
        ) THEN
            ALTER TYPE {ENUM_NAME} ADD VALUE '{NEW_TRIGGER_VALUE}';
        END IF;
    END
    $$;
    """
    )

    op.add_column(
        "automation_runs",
        sa.Column("research_thread_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        FK_NAME,
        "automation_runs",
        "research_threads",
        ["research_thread_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        INDEX_NAME,
        "automation_runs",
        ["research_thread_id"],
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="automation_runs")
    op.drop_constraint(FK_NAME, "automation_runs", type_="foreignkey")
    op.drop_column("automation_runs", "research_thread_id")
    # PostgreSQL cannot remove an enum value, so 'memory_change' remains on the
    # automation_trigger_type enum (no-op downgrade for that part, like 147).
