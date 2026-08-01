"""Add dedicated latency columns and partial index to token_usage.

Story 9.3 (T5.3): deep-research latency needs queryable percentiles per mode.

* ``token_usage.resolved_mode`` — nullable string, the mode the engine actually ran.
* ``token_usage.mode_requested`` — nullable string, the mode the caller requested.
* ``token_usage.e2e_ms`` — nullable integer, end-to-end research call duration.
* ``token_usage.ttfb_ms`` — nullable integer, time to first factual chunk.
* Partial index on ``(usage_type, resolved_mode, created_at)`` where
  ``usage_type = 'deep_research'`` and ``resolved_mode IS NOT NULL`` for fast
  percentile lookups. The ``mode_requested`` is kept for fallback grouping only.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "185"
down_revision: str | None = "184"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LATENCY_INDEX = "ix_token_usage_deep_research_resolved_mode_created_at"


def upgrade() -> None:
    op.add_column(
        "token_usage",
        sa.Column("resolved_mode", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "token_usage",
        sa.Column("mode_requested", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "token_usage",
        sa.Column("e2e_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "token_usage",
        sa.Column("ttfb_ms", sa.Integer(), nullable=True),
    )
    op.create_index(
        LATENCY_INDEX,
        "token_usage",
        ["usage_type", "resolved_mode", "created_at"],
        postgresql_where=sa.text(
            "usage_type = 'deep_research' AND resolved_mode IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(LATENCY_INDEX, table_name="token_usage")
    op.drop_column("token_usage", "ttfb_ms")
    op.drop_column("token_usage", "e2e_ms")
    op.drop_column("token_usage", "mode_requested")
    op.drop_column("token_usage", "resolved_mode")
