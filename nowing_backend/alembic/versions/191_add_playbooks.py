"""Add playbooks table and playbook lineage to automations.

Revision ID: 191
Revises: 190
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "191"
down_revision: str | None = "190"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the enum explicitly first; ``create_type=False`` on the column
    # prevents the ``CREATE TABLE`` event from trying to create it again.
    playbook_scope = sa.dialects.postgresql.ENUM(
        "workspace", "system", name="playbook_scope", create_type=False
    )
    playbook_scope.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "playbooks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("inputs_schema", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "tool_scope",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "verticals",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"general\"]'::jsonb"),
        ),
        sa.Column(
            "scope",
            playbook_scope,
            nullable=False,
            server_default="workspace",
            index=True,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_playbooks")),
    )
    # Indexes on ``scope`` and ``workspace_id`` are created automatically by
    # ``index=True`` on the columns above.

    op.add_column(
        "automations",
        sa.Column(
            "derived_from_playbook_id",
            sa.Integer(),
            sa.ForeignKey("playbooks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "automations",
        sa.Column("playbook_version", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_automations_derived_from_playbook_id"),
        "automations",
        ["derived_from_playbook_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_automations_derived_from_playbook_id"),
        table_name="automations",
    )
    op.drop_column("automations", "playbook_version")
    op.drop_column("automations", "derived_from_playbook_id")
    # ``DROP TABLE`` cascades to the indexes created by ``index=True``.
    op.drop_table("playbooks")
    sa.Enum("workspace", "system", name="playbook_scope").drop(
        op.get_bind(), checkfirst=True
    )
