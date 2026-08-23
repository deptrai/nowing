"""add workspace_apps table (Story 27.1 / AD-113 / AD-114)

Revision ID: 231
Revises: 230
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "231"
down_revision: str | None = "230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    from sqlalchemy.engine import reflection

    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("workspace_apps"):
        op.create_table(
            "workspace_apps",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "workspace_id",
                sa.Integer(),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "user_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("user.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=100), nullable=False, index=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column(
                "language",
                sa.String(length=10),
                nullable=False,
                server_default="en",
            ),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default="generated",
            ),
            sa.Column("preview_url", sa.String(length=512), nullable=True),
            sa.Column("public_url", sa.String(length=512), nullable=True),
            sa.Column("custom_domain", sa.String(length=255), nullable=True),
            sa.Column("custom_domain_status", sa.String(length=50), nullable=True),
            sa.Column("storage_path", sa.String(length=512), nullable=True),
            sa.Column("container_id", sa.String(length=100), nullable=True),
            sa.Column("port", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint(
                "workspace_id", "slug", name="uq_workspace_apps_workspace_slug"
            ),
        )
        op.create_index(
            "ix_workspace_apps_workspace_status",
            "workspace_apps",
            ["workspace_id", "status"],
        )
        op.create_index(
            "ix_workspace_apps_custom_domain",
            "workspace_apps",
            ["custom_domain"],
        )


def downgrade() -> None:
    if _table_exists("workspace_apps"):
        op.drop_index("ix_workspace_apps_custom_domain", table_name="workspace_apps")
        op.drop_index("ix_workspace_apps_workspace_status", table_name="workspace_apps")
        op.drop_table("workspace_apps")
