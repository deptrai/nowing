"""publish leads to zero_publication and align status default

Adds the ``leads`` table to ``zero_publication`` so lead status mutations
synchronize across workspace clients (Story 21.4 / AC-4), and aligns the
status default with the canonical ``new`` value used by schema and UI.

Revision ID: 203
Revises: 202
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from app.zero_publication import apply_publication

revision: str = "203"
down_revision: str | None = "202"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "leads",
        "status",
        server_default=text("'new'"),
    )
    apply_publication(op.get_bind())


def downgrade() -> None:
    """No-op. Historical publication shapes and defaults are immutable."""
