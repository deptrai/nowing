"""Add user.notification_preferences JSONB column.

Story 11.1 (FR-TELE-2, FR-TELE-1):

* Stores per-user notification preferences (e.g. Telegram automation-run
  completion) as a flexible JSONB map on the ``user`` table.
* Defaults to an empty object so existing rows stay valid.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "187"
down_revision: str | None = "affe6fa9686c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "notification_preferences",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user", "notification_preferences")
