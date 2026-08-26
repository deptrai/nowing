"""add scraper rules table

Revision ID: 050da0ff5b1e
Revises: 9a32642d01df
Create Date: 2026-08-26 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "050da0ff5b1e"
down_revision: str | None = "9a32642d01df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "scraper_rules",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "rule_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "version", name="uq_scraper_rules_platform_version"),
        sa.Index(
            "uq_scraper_rules_active_per_platform",
            "platform",
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        ),
    )
    op.create_index("ix_scraper_rules_platform", "scraper_rules", ["platform"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_scraper_rules_platform", table_name="scraper_rules")
    op.drop_table("scraper_rules")
