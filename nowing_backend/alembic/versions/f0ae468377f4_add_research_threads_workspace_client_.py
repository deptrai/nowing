"""add research_threads workspace client index

Revision ID: f0ae468377f4
Revises: f55f32bc02ed
Create Date: 2026-08-10 04:25:34.976414

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0ae468377f4'
down_revision: Union[str, None] = 'f55f32bc02ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index for vertical-client research thread lookups."""
    op.create_index(
        op.f("ix_research_threads_workspace_id_client_id"),
        "research_threads",
        ["workspace_id", "client_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop composite index."""
    op.drop_index(
        op.f("ix_research_threads_workspace_id_client_id"),
        table_name="research_threads",
    )
