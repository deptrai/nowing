"""public_agent_chat_scope

Revision ID: 78f7a9b1e85f
Revises: 3614bc146952
Create Date: 2026-08-09 22:23:47.645435

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "78f7a9b1e85f"
down_revision: str | None = "3614bc146952"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add PAT scope, vertical client, and agent registry schema for Epic 18."""

    # Enable case-insensitive text type used by client_id columns.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # 1. personal_access_tokens — PAT scope fields
    op.add_column(
        "personal_access_tokens",
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "personal_access_tokens",
        sa.Column("client_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "personal_access_tokens",
        sa.Column("agent_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "personal_access_tokens",
        sa.Column(
            "scopes",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "personal_access_tokens",
        sa.Column(
            "token_kind",
            sa.Text(),
            nullable=False,
            server_default="legacy",
        ),
    )

    op.create_index(
        op.f("ix_personal_access_tokens_workspace_id"),
        "personal_access_tokens",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personal_access_tokens_client_id"),
        "personal_access_tokens",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_personal_access_tokens_token_kind"),
        "personal_access_tokens",
        ["token_kind"],
        unique=False,
    )

    # ponytail: backfill server_default for existing created_at so raw SQL
    # inserts (e.g. admin scripts, tests) do not need an explicit timestamp.
    op.alter_column(
        "personal_access_tokens",
        "created_at",
        server_default=sa.text("now()"),
    )

    op.create_check_constraint(
        "chk_pat_agent_chat_requires_scope",
        "personal_access_tokens",
        sa.text(
            "(token_kind != 'agent_chat') OR "
            "(workspace_id IS NOT NULL AND client_id IS NOT NULL AND scopes != '[]'::jsonb)"
        ),
    )
    op.create_check_constraint(
        "chk_pat_agent_id_requires_client_id",
        "personal_access_tokens",
        sa.text("(agent_id IS NULL) OR (client_id IS NOT NULL)"),
    )

    # 2. vertical_clients — partner tenant registry
    op.create_table(
        "vertical_clients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.CITEXT(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vertical_clients")),
        sa.UniqueConstraint(
            "client_id", name=op.f("unique_vertical_clients_client_id")
        ),
    )

    # 3. agent_configs — agent registry (AD-30)
    op.create_table(
        "agent_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("system_instructions", sa.Text(), nullable=True),
        sa.Column(
            "enabled_tools",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "disabled_tools",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column(
            "citations_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_configs")),
        sa.UniqueConstraint(
            "client_id",
            "slug",
            name=op.f("unique_agent_configs_client_slug"),
        ),
    )
    op.create_index(
        op.f("ix_agent_configs_client_id"),
        "agent_configs",
        ["client_id"],
        unique=False,
    )

    # 4. client_id columns on chat/research tables
    op.add_column(
        "new_chat_threads",
        sa.Column("client_id", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_new_chat_threads_client_id"),
        "new_chat_threads",
        ["client_id"],
        unique=False,
    )

    op.add_column(
        "research_threads",
        sa.Column("client_id", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_research_threads_client_id"),
        "research_threads",
        ["client_id"],
        unique=False,
    )

    # 5. Row-level security (AD-31) — hard client_id isolation for tenant tables.
    # The application sets app.current_client_id with SET LOCAL before queries.
    for table in (
        "new_chat_threads",
        "research_threads",
        "vertical_clients",
        "agent_configs",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_client_isolation_policy
            ON {table}
            FOR ALL
            TO PUBLIC
            USING (
                client_id = current_setting('app.current_client_id', true)
                OR (
                    current_setting('app.current_client_id', true) IS NULL
                    AND client_id IS NULL
                )
            )
            WITH CHECK (
                client_id = current_setting('app.current_client_id', true)
                OR current_setting('app.current_client_id', true) IS NULL
            )
        """
        )


def downgrade() -> None:
    """Rollback Epic 18 schema additions."""
    for table in (
        "new_chat_threads",
        "research_threads",
        "vertical_clients",
        "agent_configs",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_client_isolation_policy ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_research_threads_client_id"), table_name="research_threads")
    op.drop_column("research_threads", "client_id")

    op.drop_index(op.f("ix_new_chat_threads_client_id"), table_name="new_chat_threads")
    op.drop_column("new_chat_threads", "client_id")

    op.drop_index(op.f("ix_agent_configs_client_id"), table_name="agent_configs")
    op.drop_table("agent_configs")
    op.drop_table("vertical_clients")

    op.drop_constraint(
        "chk_pat_agent_id_requires_client_id",
        "personal_access_tokens",
        type_="check",
    )
    op.drop_constraint(
        "chk_pat_agent_chat_requires_scope",
        "personal_access_tokens",
        type_="check",
    )

    op.drop_index(
        op.f("ix_personal_access_tokens_token_kind"),
        table_name="personal_access_tokens",
    )
    op.drop_index(
        op.f("ix_personal_access_tokens_client_id"), table_name="personal_access_tokens"
    )
    op.drop_index(
        op.f("ix_personal_access_tokens_workspace_id"),
        table_name="personal_access_tokens",
    )

    op.drop_column("personal_access_tokens", "token_kind")
    op.drop_column("personal_access_tokens", "scopes")
    op.drop_column("personal_access_tokens", "agent_id")
    op.drop_column("personal_access_tokens", "client_id")
    op.drop_column("personal_access_tokens", "workspace_id")
