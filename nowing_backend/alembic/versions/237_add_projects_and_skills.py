"""add project and skills hub tables

Revision ID: 237_add_projects_and_skills
Revises: 235_lead_indexing_fts_and_vector, 236
Create Date: 2026-09-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

try:
    from app.zero_publication import apply_publication
except ImportError:
    apply_publication = None

# revision identifiers, used by Alembic.
revision: str = "237_add_projects_and_skills"
down_revision: str | Sequence[str] | None = "e84a71b56b48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    from sqlalchemy.engine import reflection

    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    from sqlalchemy.engine import reflection

    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # 1. Create projects table
    if not _table_exists("projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.String(length=1000), nullable=True),
            sa.Column("master_instructions", sa.Text(), nullable=True),
            sa.Column(
                "is_archived",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["workspace_id"],
                ["workspaces.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"],
                ["user.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_projects_id", "projects", ["id"])
        op.create_index("ix_projects_name", "projects", ["name"])
        op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
        op.create_index("ix_projects_created_by_id", "projects", ["created_by_id"])
        op.create_index("ix_projects_is_archived", "projects", ["is_archived"])
        op.create_index("ix_projects_created_at", "projects", ["created_at"])
        op.create_index("ix_projects_updated_at", "projects", ["updated_at"])

    # 2. Create project_pinned_documents table
    if not _table_exists("project_pinned_documents"):
        op.create_table(
            "project_pinned_documents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column(
                "pinned_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["projects.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["document_id"],
                ["documents.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id", "document_id", name="uq_project_pinned_document"
            ),
        )
        op.create_index("ix_project_pinned_documents_id", "project_pinned_documents", ["id"])
        op.create_index("ix_project_pinned_documents_project_id", "project_pinned_documents", ["project_id"])
        op.create_index("ix_project_pinned_documents_document_id", "project_pinned_documents", ["document_id"])
        op.create_index("ix_project_pinned_documents_pinned_at", "project_pinned_documents", ["pinned_at"])

    # 3. Create workspace_skills table
    if not _table_exists("workspace_skills"):
        op.create_table(
            "workspace_skills",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("trigger_pattern", sa.String(length=255), nullable=False),
            sa.Column("content_markdown", sa.Text(), nullable=False),
            sa.Column(
                "skill_type",
                sa.String(length=50),
                nullable=False,
                server_default="prompt",
            ),
            sa.Column(
                "parameters_schema",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["workspace_id"],
                ["workspaces.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"],
                ["user.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "workspace_id", "slug", name="uq_workspace_skills_workspace_slug"
            ),
        )
        op.create_index("ix_workspace_skills_id", "workspace_skills", ["id"])
        op.create_index("ix_workspace_skills_workspace_id", "workspace_skills", ["workspace_id"])
        op.create_index("ix_workspace_skills_slug", "workspace_skills", ["slug"])
        op.create_index("ix_workspace_skills_is_active", "workspace_skills", ["is_active"])
        op.create_index("ix_workspace_skills_created_by_id", "workspace_skills", ["created_by_id"])
        op.create_index("ix_workspace_skills_created_at", "workspace_skills", ["created_at"])
        op.create_index("ix_workspace_skills_updated_at", "workspace_skills", ["updated_at"])

    # 4. Create project_skills table
    if not _table_exists("project_skills"):
        op.create_table(
            "project_skills",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("skill_id", sa.Integer(), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["projects.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["skill_id"],
                ["workspace_skills.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_id", "skill_id", name="uq_project_skills_project_skill"
            ),
        )
        op.create_index("ix_project_skills_id", "project_skills", ["id"])
        op.create_index("ix_project_skills_project_id", "project_skills", ["project_id"])
        op.create_index("ix_project_skills_skill_id", "project_skills", ["skill_id"])

    # 5. Add project_id to new_chat_threads
    if not _column_exists("new_chat_threads", "project_id"):
        op.add_column(
            "new_chat_threads",
            sa.Column("project_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_new_chat_threads_project_id_projects",
            "new_chat_threads",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_new_chat_threads_project_id",
            "new_chat_threads",
            ["project_id"],
        )

    if apply_publication:
        apply_publication(op.get_bind())


def downgrade() -> None:
    if _column_exists("new_chat_threads", "project_id"):
        op.drop_constraint(
            "fk_new_chat_threads_project_id_projects",
            "new_chat_threads",
            type_="foreignkey",
        )
        op.drop_index("ix_new_chat_threads_project_id", table_name="new_chat_threads")
        op.drop_column("new_chat_threads", "project_id")

    if _table_exists("project_skills"):
        op.drop_table("project_skills")

    if _table_exists("workspace_skills"):
        op.drop_table("workspace_skills")

    if _table_exists("project_pinned_documents"):
        op.drop_table("project_pinned_documents")

    if _table_exists("projects"):
        op.drop_table("projects")
