"""add scraper_platform_accounts

Revision ID: affe6fa9686c
Revises: 186
Create Date: 2026-08-03 11:20:56.302424

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'affe6fa9686c'
down_revision: str | None = '186'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('scraper_platform_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('encrypted_credentials', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scraper_platform_accounts_created_at'), 'scraper_platform_accounts', ['created_at'], unique=False)
    op.create_index(op.f('ix_scraper_platform_accounts_id'), 'scraper_platform_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_scraper_platform_accounts_platform'), 'scraper_platform_accounts', ['platform'], unique=False)
    op.create_index('uq_scraper_platform_accounts_default', 'scraper_platform_accounts', ['platform'], unique=True, postgresql_where=sa.text('is_default = true'))


def downgrade() -> None:
    op.drop_index('uq_scraper_platform_accounts_default', table_name='scraper_platform_accounts')
    op.drop_index(op.f('ix_scraper_platform_accounts_platform'), table_name='scraper_platform_accounts')
    op.drop_index(op.f('ix_scraper_platform_accounts_id'), table_name='scraper_platform_accounts')
    op.drop_index(op.f('ix_scraper_platform_accounts_created_at'), table_name='scraper_platform_accounts')
    op.drop_column('scraper_platform_accounts', 'updated_at')
    op.drop_table('scraper_platform_accounts')
