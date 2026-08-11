"""add_memory_source_uuid_entity_type

Revision ID: e5b50d5e687e
Revises: 2c422d15105e
Create Date: 2026-08-11 18:26:11.617807

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5b50d5e687e'
down_revision: str | None = '2c422d15105e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add soft UUID provenance columns that the ORM already declares (AD-44)."""
    op.add_column(
        "memories",
        sa.Column(
            "source_uuid",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "memories",
        sa.Column(
            "source_entity_type",
            sa.String(100),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_memories_source_uuid",
        "memories",
        ["source_uuid"],
    )


def downgrade() -> None:
    """Remove the soft UUID provenance columns."""
    op.drop_index("ix_memories_source_uuid", table_name="memories")
    op.drop_column("memories", "source_entity_type")
    op.drop_column("memories", "source_uuid")
