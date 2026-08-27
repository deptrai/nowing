"""drop lead client_id from zero_publication (revised)

Revision ID: 142d54696fd7
Revises: 3e0decbbbfbf
Create Date: 2026-08-27 08:53:14.240985

"""

from collections.abc import Sequence

from alembic import op
from app.zero_publication import apply_publication

# revision identifiers, used by Alembic.
revision: str = "142d54696fd7"
down_revision: str | None = "3e0decbbbfbf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # The original ALTER COLUMN ... TYPE rewrite for client_id proved too
    # expensive for production lead tables and could block on the publication.
    # The canonical zero_publication definition now excludes client_id, which
    # is still available over REST. Reconcile the publication to that shape.
    apply_publication(bind)


def downgrade() -> None:
    bind = op.get_bind()
    apply_publication(bind)
