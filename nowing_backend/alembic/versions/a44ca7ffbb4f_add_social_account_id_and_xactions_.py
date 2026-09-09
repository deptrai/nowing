"""add social account id and xactions proxy bindings

Revision ID: a44ca7ffbb4f
Revises: a2e8e71315bc
Create Date: 2026-09-09 08:38:20.652226

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a44ca7ffbb4f'
down_revision: str | None = 'a2e8e71315bc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add account_id column to social_monitored_targets
    op.add_column(
        'social_monitored_targets',
        sa.Column('account_id', sa.String(length=255), nullable=True)
    )

    # Add new columns to social_posts for thin-event payload
    op.add_column(
        'social_posts',
        sa.Column('category', sa.String(length=50), nullable=True, server_default='general')
    )
    op.add_column(
        'social_posts',
        sa.Column('storage_ref', sa.Text(), nullable=True)
    )
    op.add_column(
        'social_posts',
        sa.Column('scraper_id', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'social_posts',
        sa.Column('benchmark_health', sa.String(length=10), nullable=True)
    )
    op.add_column(
        'social_posts',
        sa.Column('benchmark_alert', sa.Boolean(), nullable=True, server_default=sa.false())
    )

    # Create xactions_proxy_bindings table
    op.create_table(
        'xactions_proxy_bindings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.String(length=255), nullable=False),
        sa.Column('proxy_url', sa.Text(), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_bound_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'account_id', 'platform', name='uq_xactions_proxy_binding')
    )
    op.create_index(
        'idx_xactions_proxy_bindings_workspace_id',
        'xactions_proxy_bindings',
        ['workspace_id'],
        unique=False
    )
    op.create_index(
        'idx_xactions_proxy_bindings_active',
        'xactions_proxy_bindings',
        ['is_active'],
        unique=False
    )


def downgrade() -> None:
    op.drop_table('xactions_proxy_bindings')
    op.drop_column('social_posts', 'benchmark_alert')
    op.drop_column('social_posts', 'benchmark_health')
    op.drop_column('social_posts', 'scraper_id')
    op.drop_column('social_posts', 'storage_ref')
    op.drop_column('social_posts', 'category')
    op.drop_column('social_monitored_targets', 'account_id')
