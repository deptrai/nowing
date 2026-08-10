"""CR-18.3 review patch

Revision ID: b870a82a7e81
Revises: c826c8e6e149
Create Date: 2026-08-10 18:28:18.504643

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by this migration.
revision: str = "b870a82a7e81"
down_revision: str | None = "c826c8e6e149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owner_clause(table: str) -> str:
    if table in ("new_chat_threads", "research_threads"):
        return (
            " OR created_by_id IS NOT DISTINCT FROM "
            "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
        )
    return ""


def _create_policy(table: str, with_bypass: bool) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_client_isolation_policy ON {table}")
    bypass = ""
    if with_bypass:
        bypass = " OR current_setting('app.internal_service', true) = 'true'"
    owner = _owner_clause(table)
    op.execute(
        f"""
        CREATE POLICY {table}_client_isolation_policy
        ON {table}
        FOR ALL
        TO PUBLIC
        USING (
            client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
            {owner}
            {bypass}
        )
        WITH CHECK (
            client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
            {owner}
            {bypass}
        )
    """
    )


def upgrade() -> None:
    """Apply review patch for Story 18.3."""
    # 1. Add display_name to agent_configs (required by UX contract).
    op.add_column(
        "agent_configs",
        sa.Column("display_name", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE agent_configs SET display_name = name WHERE display_name IS NULL"
    )
    op.alter_column(
        "agent_configs",
        "display_name",
        existing_type=sa.Text(),
        nullable=False,
    )

    # 2. Enforce name uniqueness per client (story subtask / UX contract).
    op.create_unique_constraint(
        "unique_agent_configs_client_name",
        "agent_configs",
        ["client_id", "name"],
    )

    # 3. Fix citations_enabled default: spec says default true.
    op.alter_column(
        "agent_configs",
        "citations_enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default="true",
    )
    op.execute(
        "UPDATE agent_configs SET citations_enabled = true WHERE citations_enabled = false"
    )

    # 4. Add app.internal_service bypass to RLS policies so platform admin
    #    routes can read/write rows when no single client GUC is appropriate.
    for table in (
        "new_chat_threads",
        "research_threads",
        "vertical_clients",
        "agent_configs",
    ):
        _create_policy(table, with_bypass=True)


def downgrade() -> None:
    """Rollback CR-18.3 review patch."""
    for table in (
        "new_chat_threads",
        "research_threads",
        "vertical_clients",
        "agent_configs",
    ):
        _create_policy(table, with_bypass=False)

    op.alter_column(
        "agent_configs",
        "citations_enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default="false",
    )

    op.drop_constraint(
        "unique_agent_configs_client_name",
        "agent_configs",
        type_="unique",
    )
    op.drop_column("agent_configs", "display_name")
