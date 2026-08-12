"""alter memory client_id columns to citext

Revision ID: ea7aca64ccff
Revises: b8b3fae31175
Create Date: 2026-08-12 11:40:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea7aca64ccff"
down_revision: str | None = "b8b3fae31175"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _memory_tenant_predicate(table: str) -> str:
    """Composite workspace + client predicate with CITEXT cast for client_id."""
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
        AND {table}.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')::citext
    """


def _memory_id_predicate(table: str) -> str:
    return f"{table}.id::text = current_setting('app.memory_id', true)"


def _internal_service_predicate(_table: str) -> str:
    return "current_setting('app.internal_service', true) = 'true'"


def _drop_policies(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table};")
    op.execute(f"DROP POLICY IF EXISTS {table}_internal_service_policy ON {table};")


def _create_rls(table: str, *, include_memory_id: bool) -> None:
    _drop_policies(table)
    extras = ""
    if include_memory_id:
        extras = f" OR {_memory_id_predicate(table)}"
    op.execute(f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING (
                {_memory_tenant_predicate(table)}
                {extras}
                OR {_internal_service_predicate(table)}
            );
    """)
    op.execute(f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_memory_tenant_predicate(table)})
            WITH CHECK ({_memory_tenant_predicate(table)});
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


def _alter_client_id(table: str, type_name: str) -> None:
    """Change the column type, optionally through an explicit cast."""
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN client_id TYPE "
        f"{type_name} USING client_id::{type_name}"
    )


def upgrade() -> None:
    """Make memory client_id columns CITEXT to match VerticalClient.client_id.

    ``client_id`` is a vertical-client natural key; CITEXT prevents
    case-sensitivity mismatches between memory rows and the canonical
    client key (AD-31). The RLS predicates that gate access on this
    column are updated to compare against a ``citext``-cast GUC so the
    comparison remains case-insensitive.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    # Policies must be dropped before the column type can be altered,
    # then re-created with the matching predicate cast.
    _drop_policies("memories")
    _drop_policies("memory_relations")
    _alter_client_id("memories", "citext")
    _alter_client_id("memory_relations", "citext")
    _create_rls("memories", include_memory_id=True)
    _create_rls("memory_relations", include_memory_id=False)


def _legacy_tenant_predicate(table: str) -> str:
    """Original text client_id predicate for use after column downgrade."""
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
        AND {table}.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
    """


def _create_legacy_rls(table: str, *, include_memory_id: bool) -> None:
    _drop_policies(table)
    extras = ""
    if include_memory_id:
        extras = f" OR {_memory_id_predicate(table)}"
    op.execute(f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING (
                {_legacy_tenant_predicate(table)}
                {extras}
                OR {_internal_service_predicate(table)}
            );
    """)
    op.execute(f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_legacy_tenant_predicate(table)})
            WITH CHECK ({_legacy_tenant_predicate(table)});
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


def downgrade() -> None:
    """Revert client_id columns to plain text."""
    _drop_policies("memories")
    _drop_policies("memory_relations")
    _alter_client_id("memories", "text")
    _alter_client_id("memory_relations", "text")
    _create_legacy_rls("memories", include_memory_id=True)
    _create_legacy_rls("memory_relations", include_memory_id=False)
