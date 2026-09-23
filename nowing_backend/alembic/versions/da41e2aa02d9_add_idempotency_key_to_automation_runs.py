"""add idempotency_key to automation_runs

Revision ID: da41e2aa02d9
Revises: 5bd0001357ae
Create Date: 2026-09-10 19:39:02.484321

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da41e2aa02d9'
down_revision: Union[str, None] = '5bd0001357ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add idempotency_key column to automation_runs."""
    op.add_column(
        "automation_runs",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_automation_runs_idempotency_key",
        "automation_runs",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    """Remove idempotency_key column from automation_runs."""
    op.drop_index("ix_automation_runs_idempotency_key", table_name="automation_runs")
    op.drop_column("automation_runs", "idempotency_key")
