"""remove client_id from lead zero publication

Revision ID: 4c04ec8dda06
Revises: 142d54696fd7
Create Date: 2026-08-27 10:10:00.000000

"""

from collections.abc import Sequence

from alembic import op
from app.zero_publication import apply_publication

# revision identifiers, used by Alembic.
revision: str = "4c04ec8dda06"
down_revision: str | None = "142d54696fd7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # Ensure the canonical zero_publication excludes client_id for lead tables.
    # This is idempotent and only emits DDL if the shape has drifted.
    apply_publication(bind)


def downgrade() -> None:
    bind = op.get_bind()
    apply_publication(bind)
