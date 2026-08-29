"""remove client_id from lead zero publication

Zero does not support the CITEXT type. Lead tables keep client_id as CITEXT
in Postgres for case-insensitive vertical-client scoping, but that column is
excluded from the zero_publication column lists so zero-cache can sync the
tables without reloading.

Revision ID: 3e0decbbbfbf
Revises: 234_add_memory_retention
Create Date: 2026-08-27 08:21:27.158161

"""

from collections.abc import Sequence

from alembic import op
from app.zero_publication import apply_publication

# revision identifiers, used by Alembic.
revision: str = "3e0decbbbfbf"
down_revision: str | None = "234_add_memory_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reconcile zero_publication to the new canonical shape."""
    apply_publication(op.get_bind())


def downgrade() -> None:
    """Re-apply the previous publication shape."""
    apply_publication(op.get_bind())
