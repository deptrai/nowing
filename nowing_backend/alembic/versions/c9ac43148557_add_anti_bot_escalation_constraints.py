"""add anti bot escalation constraints

Revision ID: c9ac43148557
Revises: 197
Create Date: 2026-08-09 11:42:34.766073

"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c9ac43148557"
down_revision: Union[str, None] = "197"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add partial unique index for open grouping and status CHECK."""
    # 1. Drop the old non-unique composite index first to avoid conflicts.
    op.drop_index(
        "ix_anti_bot_escalations_workspace_domain_cap_status",
        table_name="anti_bot_escalations",
    )

    # 2. Add a CHECK constraint for the allowed status values (works with text).
    op.create_check_constraint(
        "ck_anti_bot_escalations_status",
        "anti_bot_escalations",
        sa.text("status IN ('open', 'resolved', 'retry')"),
    )

    # 3. Tighten status to a native ENUM. Drop default first to avoid cast errors.
    status_enum = postgresql.ENUM(
        "open", "resolved", "retry", name="anti_bot_escalation_status"
    )
    status_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE anti_bot_escalations ALTER COLUMN status DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE anti_bot_escalations ALTER COLUMN status "
        "TYPE anti_bot_escalation_status USING status::anti_bot_escalation_status"
    )
    op.execute(
        "ALTER TABLE anti_bot_escalations ALTER COLUMN status SET DEFAULT 'open'"
    )

    # 4. Create the partial unique index now that status is an enum.
    # ponytail: partial unique index enforces AC #5 grouping at DB level.
    op.create_index(
        "ix_anti_bot_escalations_grouping_open_unique",
        "anti_bot_escalations",
        ["workspace_id", "domain", "capability"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    """Remove constraints added in this revision."""
    op.drop_index(
        "ix_anti_bot_escalations_grouping_open_unique",
        table_name="anti_bot_escalations",
    )

    op.execute(
        "ALTER TABLE anti_bot_escalations ALTER COLUMN status DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE anti_bot_escalations ALTER COLUMN status TYPE VARCHAR(16)"
    )
    op.execute(
        "ALTER TABLE anti_bot_escalations ALTER COLUMN status SET DEFAULT 'open'"
    )
    status_enum = postgresql.ENUM(
        "open", "resolved", "retry", name="anti_bot_escalation_status"
    )
    status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_constraint(
        "ck_anti_bot_escalations_status",
        "anti_bot_escalations",
        type_="check",
    )

    op.create_index(
        "ix_anti_bot_escalations_workspace_domain_cap_status",
        "anti_bot_escalations",
        ["workspace_id", "domain", "capability", "status"],
        unique=False,
    )
