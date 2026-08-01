"""Add source capability and input recipe to memories.

Story 9.6a (FR-39, AD-11.1):

* ``memories.source_capability`` — nullable string holding the ``Run.capability``
  that produced a scraper-run-derived memory (e.g. ``"reddit.scrape"``).
* ``memories.source_input`` — nullable JSONB snapshot of ``Run.input`` so the
  query can be re-executed for re-validation even after the 30-day ``runs``
  retention cleanup deletes the original run log.

Both are deliberately soft copies: ``runs`` is a short-lived log, while
``memories`` is durable first-class storage. ``source_input`` is an immutable
snapshot; a new query requires a new memory, not a mutated recipe.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "186"
down_revision: str | None = "185"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column(
            "source_capability",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "memories",
        sa.Column(
            "source_input",
            postgresql.JSONB,
            nullable=True,
        ),
    )

    # Story 9.6a: backfill recipe for existing run-derived memories whose
    # source run log is still present. Runs have a ~30 day retention, so this
    # only helps deployments that upgrade soon after the run was created, but
    # it keeps the migration self-contained and avoids leaving a data gap for
    # fresh upgrades.
    op.execute(
        sa.text(
            "UPDATE memories "
            "SET source_capability = runs.capability, "
            "    source_input = runs.input "
            "FROM runs "
            "WHERE memories.source_run_id = runs.id "
            "  AND memories.source_capability IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("memories", "source_input")
    op.drop_column("memories", "source_capability")
