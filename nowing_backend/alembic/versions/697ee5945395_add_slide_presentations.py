"""add slide presentations

Revision ID: 697ee5945395
Revises: 75fdfe2368ae
Create Date: 2026-08-25 19:51:32.604680

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "697ee5945395"
down_revision: str | None = "75fdfe2368ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "slide_presentations",
        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column(
            "format",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'pptx'"),
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'generating'"),
        ),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("preview_url", sa.String(length=512), nullable=True),
        sa.Column("slide_count", sa.Integer(), nullable=True),
        sa.Column("degradation_reason", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "slug",
            name="uq_slide_presentations_workspace_slug",
        ),
    )
    op.create_index(
        "ix_slide_presentations_workspace_id",
        "slide_presentations",
        ["workspace_id"],
    )
    op.create_index(
        "ix_slide_presentations_user_id",
        "slide_presentations",
        ["user_id"],
    )
    op.create_index(
        "ix_slide_presentations_workspace_status",
        "slide_presentations",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_slide_presentations_workspace_status", table_name="slide_presentations"
    )
    op.drop_index("ix_slide_presentations_user_id", table_name="slide_presentations")
    op.drop_index(
        "ix_slide_presentations_workspace_id", table_name="slide_presentations"
    )
    op.drop_table("slide_presentations")
