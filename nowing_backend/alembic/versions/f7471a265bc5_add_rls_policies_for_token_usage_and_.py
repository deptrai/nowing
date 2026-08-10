"""add rls policies for token_usage

Revision ID: f7471a265bc5
Revises: 50461b6ab1cd
Create Date: 2026-08-10 10:19:38.667197

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7471a265bc5'
down_revision: str | None = '50461b6ab1cd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _workspace_predicate(table: str) -> str:
    """Workspace-only read predicate."""
    return f"{table}.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int"


def _tenant_predicate(table: str) -> str:
    """Composite workspace + client predicate for writes."""
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int
        AND {table}.client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)
    """


def _drop_policies(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table};")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _create_rls(table: str) -> None:
    _drop_policies(table)
    op.execute(f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING ({_workspace_predicate(table)});
    """)
    op.execute(f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_tenant_predicate(table)})
            WITH CHECK ({_tenant_predicate(table)});
    """)
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    """Enable workspace/client RLS on token_usage."""
    _create_rls("token_usage")


def downgrade() -> None:
    """Remove RLS policies."""
    _drop_policies("token_usage")
