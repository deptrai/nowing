"""add web_builder_enabled to workspaces and web_builder:create permission (Story 27.1a)

Revision ID: 232
Revises: 231
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "232"
down_revision: str | None = "231"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    from sqlalchemy.engine import reflection
    bind = op.get_context().bind
    inspector = reflection.Inspector.from_engine(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    from sqlalchemy.engine import reflection
    bind = op.get_context().bind
    inspector = reflection.Inspector.from_engine(bind)
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    if _table_exists("workspaces") and not _column_exists("workspaces", "web_builder_enabled"):
        op.add_column(
            "workspaces",
            sa.Column(
                "web_builder_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )

    # Backfill the Editor system role with the new web_builder:create permission.
    op.execute(
        """
        UPDATE workspace_roles
        SET permissions = array_append(permissions, 'web_builder:create')
        WHERE name = 'Editor'
          AND is_system_role = true
          AND NOT 'web_builder:create' = ANY(permissions);
        """
    )


def downgrade() -> None:
    if _table_exists("workspaces") and _column_exists("workspaces", "web_builder_enabled"):
        op.drop_column("workspaces", "web_builder_enabled")

    op.execute(
        """
        UPDATE workspace_roles
        SET permissions = array_remove(permissions, 'web_builder:create')
        WHERE name = 'Editor'
          AND is_system_role = true;
        """
    )
