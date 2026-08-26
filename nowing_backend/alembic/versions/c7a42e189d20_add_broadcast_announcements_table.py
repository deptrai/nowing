"""add broadcast announcements table

Revision ID: c7a42e189d20
Revises: 050da0ff5b1e
Create Date: 2026-08-27 00:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.zero_publication import apply_publication

# revision identifiers, used by Alembic.
revision: str = "c7a42e189d20"
down_revision: str | None = "050da0ff5b1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "broadcast_announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "banner_type",
            sa.String(length=20),
            server_default=sa.text("'info'"),
            nullable=False,
        ),
        sa.Column(
            "target_all", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "target_workspace_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "starts_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "dismissible", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
    )
    op.create_index(
        "ix_broadcast_announcements_created_by_user_id",
        "broadcast_announcements",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_broadcast_announcements_active_window",
        "broadcast_announcements",
        ["is_active", "starts_at", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_broadcast_announcements_target_workspace_ids",
        "broadcast_announcements",
        ["target_workspace_ids"],
        unique=False,
        postgresql_using="gin",
    )
    apply_publication(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_broadcast_announcements_target_workspace_ids",
        table_name="broadcast_announcements",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_broadcast_announcements_active_window",
        table_name="broadcast_announcements",
    )
    op.drop_index(
        "ix_broadcast_announcements_created_by_user_id",
        table_name="broadcast_announcements",
    )
    op.drop_table("broadcast_announcements")
    apply_publication(op.get_bind())
