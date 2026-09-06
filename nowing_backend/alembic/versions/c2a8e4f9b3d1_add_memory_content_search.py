"""add_memory_content_search

Revision ID: c2a8e4f9b3d1
Revises: 8f4c78216b02
Create Date: 2026-09-06 09:20:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2a8e4f9b3d1"
down_revision: Union[str, None] = "8f4c78216b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ``content_search`` stores a tsvector literal derived from plaintext
    # content before encryption so keyword ranking can run without decrypting
    # every row.  Column is nullable so legacy rows remain unchanged.
    op.add_column(
        "memories",
        sa.Column("content_search", sa.Text(), nullable=True),
    )
    # GIN index on the stored tsvector literal.  Query side uses
    # ``to_tsquery('english', query)`` against ``content_search::tsvector``.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_content_search_tsvector ON memories "
        "USING gin ((content_search::tsvector));"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_content_search_tsvector;")
    op.drop_column("memories", "content_search")
