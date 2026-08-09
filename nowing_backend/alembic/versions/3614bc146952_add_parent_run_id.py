"""add parent run id

Revision ID: 3614bc146952
Revises: c9ac43148557
Create Date: 2026-08-09 11:50:28.410119

"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3614bc146952"
down_revision: Union[str, None] = "c9ac43148557"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parent_run_id to runs for retry provenance."""
    op.add_column(
        "runs",
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_runs_parent_run_id",
        "runs",
        ["parent_run_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove parent_run_id column."""
    op.drop_index("ix_runs_parent_run_id", table_name="runs")
    op.drop_column("runs", "parent_run_id")
