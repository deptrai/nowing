"""add memories rls policies

Revision ID: da595e4c316a
Revises: 7c4fc2d307b2
Create Date: 2026-08-10 11:30:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'da595e4c316a'
down_revision: str | None = '7c4fc2d307b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_predicate(table: str) -> str:
    """Composite workspace + client predicate."""
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
        AND {table}.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
    """


def _memory_id_predicate(table: str) -> str:
    """Row-capability token: a session that knows a memory id can read it."""
    return f"{table}.id::text = current_setting('app.memory_id', true)"


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
                OR {_memory_id_predicate(table)}
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

    # The L1 RLS suite runs under a dedicated application role that must not
    # bypass RLS and must be able to touch this table.
    op.execute("""
        DO $$
        BEGIN
            CREATE ROLE nowing_app NOLOGIN NOBYPASSRLS;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END
        $$;
    """)
    op.execute("GRANT USAGE ON SCHEMA public TO nowing_app;")
    op.execute(f"GRANT ALL ON {table} TO nowing_app;")


def upgrade() -> None:
    """Enable workspace/client RLS on memories."""
    _create_rls("memories")


def downgrade() -> None:
    """Remove RLS policies and revoke app-role grants on memories."""
    _drop_policies("memories")
    op.execute("REVOKE ALL PRIVILEGES ON memories FROM nowing_app;")
