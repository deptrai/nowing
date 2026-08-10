"""add rls for runs

Revision ID: 7c4fc2d307b2
Revises: f7471a265bc5
Create Date: 2026-08-10 10:29:58.138451

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7c4fc2d307b2'
down_revision: str | None = 'f7471a265bc5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _workspace_read_predicate(table: str) -> str:
    """Workspace-only read predicate for run listings."""
    return f"{table}.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int"


def _run_token_predicate(table: str) -> str:
    """Row-capability token: a session that knows a run id can read it."""
    return f"{table}.id::text = current_setting('app.run_id', true)"


def _tenant_write_predicate(table: str) -> str:
    """Composite workspace + client predicate for writes."""
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int
        AND {table}.client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)
    """


def _drop_policies(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_internal_service_policy ON {table};")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _internal_service_predicate(_table: str) -> str:
    return "current_setting('app.internal_service', true) = 'true'"


def _create_rls(table: str) -> None:
    _drop_policies(table)
    op.execute(f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING (
                {_workspace_read_predicate(table)}
                OR {_run_token_predicate(table)}
                OR {_internal_service_predicate(table)}
            );
    """)
    op.execute(f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_tenant_write_predicate(table)})
            WITH CHECK ({_tenant_write_predicate(table)});
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
    """Enable workspace/client/run-token RLS on runs."""
    _create_rls("runs")


def downgrade() -> None:
    """Remove RLS policies."""
    _drop_policies("runs")
