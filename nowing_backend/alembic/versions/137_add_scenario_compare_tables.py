"""137_add_scenario_compare_tables - Scenario results and comparison cache

Revision ID: 137
Revises: 136

Adds scenario_results and compare_results tables for Story 9-UX-3:
- scenario_results: cache re-synthesized content per (thread_id, scenario, assumptions_hash)
- compare_results: cache token comparison data per (primary_token, secondary_token)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "137"
down_revision: str | None = "136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(conn, name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = :n"
            ),
            {"n": name},
        ).fetchone()
        is not None
    )


def _index_exists(conn, name: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": name},
        ).fetchone()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "scenario_results"):
        op.create_table(
            "scenario_results",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("thread_id", sa.Integer(), nullable=False),
            sa.Column("scenario", sa.String(length=32), nullable=False),
            sa.Column("assumptions_hash", sa.String(length=64), nullable=False),
            sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    # Re-create index defensively — covers the partial-creation case where the
    # table existed but the index did not (e.g. interrupted previous run)
    if not _index_exists(conn, "ix_scenario_results_lookup"):
        op.create_index(
            "ix_scenario_results_lookup",
            "scenario_results",
            ["thread_id", "scenario", "assumptions_hash"],
        )

    if not _table_exists(conn, "compare_results"):
        op.create_table(
            "compare_results",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            # 50 chars matches ORM `db.py:CompareResult` definition
            sa.Column("primary_token", sa.String(length=50), nullable=False),
            sa.Column("secondary_token", sa.String(length=50), nullable=False),
            sa.Column("primary_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("secondary_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("verdict", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            # Unique constraint prevents concurrent INSERT races accumulating
            # duplicate cache rows for the same (primary, secondary) pair.
            sa.UniqueConstraint(
                "primary_token", "secondary_token", name="uq_compare_results_pair"
            ),
        )

    if not _index_exists(conn, "ix_compare_results_lookup"):
        op.create_index(
            "ix_compare_results_lookup",
            "compare_results",
            ["primary_token", "secondary_token"],
        )


def downgrade() -> None:
    op.drop_index("ix_compare_results_lookup", table_name="compare_results")
    op.drop_table("compare_results")
    op.drop_index("ix_scenario_results_lookup", table_name="scenario_results")
    op.drop_table("scenario_results")
