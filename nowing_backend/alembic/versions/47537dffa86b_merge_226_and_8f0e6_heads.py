"""merge 226 and 8f0e6 heads

Revision ID: 47537dffa86b
Revises: 226, 8f0e6aa7aa87
Create Date: 2026-08-19 15:06:11.540944

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "47537dffa86b"
down_revision: str | None = ("226", "8f0e6aa7aa87")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
