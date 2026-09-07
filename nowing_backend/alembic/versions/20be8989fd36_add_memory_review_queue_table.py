"""add memory_review_queue table

Revision ID: 20be8989fd36
Revises: f6a7b8c9d0e1
Create Date: 2026-09-07 21:48:01.020211

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20be8989fd36'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'memory_review_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('memory_id', sa.Integer(), sa.ForeignKey('memories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flag_reason', sa.Text(), nullable=False),
        sa.Column('flagged_by', sa.UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_memory_review_queue_memory_id', 'memory_review_queue', ['memory_id'])
    op.create_index('ix_memory_review_queue_workspace_id', 'memory_review_queue', ['workspace_id'])
    op.create_index('ix_memory_review_queue_status', 'memory_review_queue', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('memory_review_queue')
