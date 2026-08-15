"""Alembic migration 200 round-trip test (Story 21.3, AC-3 / AD-31).

Verifies that ``200_add_enrichment_contact_tables.py`` creates the
``enrichment_requests`` and ``verified_contacts`` tables with the AD-31
indexes, and that ``downgrade()`` removes them. The test DB is built by
``Base.metadata.create_all``, so the tables already exist; the test drops them
inside the fixture transaction, runs ``upgrade()``, asserts the tables and
indexes reappear, then runs ``downgrade()`` and asserts they vanish.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.lead_intelligence]

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "200_add_enrichment_contact_tables.py"
)


def _load_migration():
    """Load the migration by file path (alembic version files are not importable)."""
    spec = importlib.util.spec_from_file_location("_migration_200", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 200 spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration(sync_conn, fn_name: str) -> None:
    """Invoke ``upgrade()``/``downgrade()`` with ``op`` bound to ``sync_conn``."""
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    module = _load_migration()
    ctx = MigrationContext.configure(connection=sync_conn)
    with Operations.context(ctx):
        getattr(module, fn_name)()


async def _table_exists(db_session: AsyncSession, table: str) -> bool:
    result = await db_session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": table},
    )
    return result.scalar_one_or_none() is not None


async def _index_exists(db_session: AsyncSession, index: str) -> bool:
    result = await db_session.execute(
        text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :i"),
        {"i": index},
    )
    return result.scalar_one_or_none() is not None


async def _column_type(db_session: AsyncSession, table: str, column: str) -> str | None:
    return (
        await db_session.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
    ).scalar_one_or_none()


async def _drop_tables(db_session: AsyncSession) -> None:
    """Return the schema to its pre-200 shape so ``upgrade()`` has work to do."""
    await db_session.execute(text("DROP TABLE IF EXISTS verified_contacts"))
    await db_session.execute(text("DROP TABLE IF EXISTS enrichment_requests"))
    await db_session.flush()


async def test_upgrade_creates_enrichment_and_contact_tables(db_session: AsyncSession):
    """AC-3 / AD-31: both tables are created with the expected columns/indexes."""
    _load_migration()
    await _drop_tables(db_session)
    assert not await _table_exists(db_session, "enrichment_requests")
    assert not await _table_exists(db_session, "verified_contacts")

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _table_exists(db_session, "enrichment_requests")
    assert await _table_exists(db_session, "verified_contacts")
    # AD-31: workspace_id + client_id indexes exist on both tables.
    assert await _index_exists(db_session, "ix_enrichment_requests_workspace_id")
    assert await _index_exists(db_session, "ix_enrichment_requests_client_id")
    assert await _index_exists(db_session, "ix_enrichment_requests_lead_id")
    assert await _index_exists(db_session, "ix_verified_contacts_workspace_id")
    assert await _index_exists(db_session, "ix_verified_contacts_client_id")
    assert await _index_exists(db_session, "ix_verified_contacts_lead_id")
    # AD-45: client_id is CITEXT; provider_results is JSONB.
    assert (
        await _column_type(db_session, "enrichment_requests", "client_id")
        == "USER-DEFINED"
    )
    assert (
        await _column_type(db_session, "enrichment_requests", "provider_results")
        == "jsonb"
    )
    assert (
        await _column_type(db_session, "verified_contacts", "email") == "USER-DEFINED"
    )
    # Task 3.1: requested_count is persisted for the async waterfall.
    assert (
        await _column_type(db_session, "enrichment_requests", "requested_count")
        == "integer"
    )


async def test_downgrade_drops_enrichment_and_contact_tables(db_session: AsyncSession):
    """A full downgrade removes both tables added by 200."""
    _load_migration()
    await _drop_tables(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "downgrade"))

    assert not await _table_exists(db_session, "enrichment_requests")
    assert not await _table_exists(db_session, "verified_contacts")
