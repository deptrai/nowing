"""add_memory_relation_client_id_and_rls

Revision ID: b8b3fae31175
Revises: 43c1895ff09a
Create Date: 2026-08-11 18:55:44.487305

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8b3fae31175'
down_revision: str | None = '43c1895ff09a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_predicate(table: str) -> str:
    """Composite workspace + client predicate."""
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
        AND {table}.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
    """


def _internal_service_predicate(_table: str) -> str:
    return "current_setting('app.internal_service', true) = 'true'"


def _drop_policies(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_internal_service_policy ON {table};")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _create_rls(table: str) -> None:
    _drop_policies(table)
    op.execute(f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING (
                {_tenant_predicate(table)}
                OR {_internal_service_predicate(table)}
            );
    """)
    op.execute(f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_tenant_predicate(table)})
            WITH CHECK ({_tenant_predicate(table)});
    """)
    op.execute(f"""
        CREATE POLICY {table}_internal_service_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_internal_service_predicate(table)})
            WITH CHECK ({_internal_service_predicate(table)});
    """)
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def upgrade() -> None:
    """Add client_id to memory_relations and enable composite RLS."""
    op.add_column(
        "memory_relations",
        sa.Column("client_id", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_memory_relations_workspace_id_client_id",
        "memory_relations",
        ["workspace_id", "client_id"],
    )
    _create_rls("memory_relations")

    # The L1 RLS suite runs under a dedicated application role that must not
    # bypass RLS; ensure it can still read/write the table through policies.
    op.execute(
        """
        DO $$
        BEGIN
            CREATE ROLE nowing_app NOLOGIN NOBYPASSRLS;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO nowing_app;")
    op.execute("GRANT ALL ON memory_relations TO nowing_app;")


def downgrade() -> None:
    """Remove client_id and RLS from memory_relations."""
    _drop_policies("memory_relations")
    op.drop_index(
        "ix_memory_relations_workspace_id_client_id",
        table_name="memory_relations",
    )
    op.drop_column("memory_relations", "client_id")
