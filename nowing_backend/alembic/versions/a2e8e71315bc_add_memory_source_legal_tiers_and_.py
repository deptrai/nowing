"""add memory_source_legal_tiers and workspace scrape_paused

Revision ID: a2e8e71315bc
Revises: 20be8989fd36
Create Date: 2026-09-08 17:14:44.588609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2e8e71315bc'
down_revision: Union[str, None] = '20be8989fd36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Story 29.6: source risk tier mapping used by governance console.
    op.create_table(
        'memory_source_legal_tiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('risk_tier', sa.String(length=20), nullable=False),
        sa.Column('recommended_retention_days', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_type', name='uq_memory_source_legal_tiers_source_type'),
    )
    op.create_index(
        'ix_memory_source_legal_tiers_source_type',
        'memory_source_legal_tiers',
        ['source_type'],
    )
    op.create_index(
        'ix_memory_source_legal_tiers_risk_tier',
        'memory_source_legal_tiers',
        ['risk_tier'],
    )

    # Soft pause marker for high-risk source tier changes. Reuses
    # api_access_enabled for the actual gate, but scrape_paused_at records
    # when and why scraping was paused by governance action.
    op.add_column(
        'workspaces',
        sa.Column('scrape_paused_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_workspaces_scrape_paused_at',
        'workspaces',
        ['scrape_paused_at'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_workspaces_scrape_paused_at', table_name='workspaces')
    op.drop_column('workspaces', 'scrape_paused_at')
    op.drop_index('ix_memory_source_legal_tiers_risk_tier', table_name='memory_source_legal_tiers')
    op.drop_index('ix_memory_source_legal_tiers_source_type', table_name='memory_source_legal_tiers')
    op.drop_table('memory_source_legal_tiers')
