"""Alembic migration 247 round-trip test (Story 41.2).

Verifies that ``247_add_leads_metadata_column.py`` adds the ``metadata`` JSONB
column to the ``leads`` table, and that ``downgrade()`` drops it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "247_add_leads_metadata_column.py"
)


def _load_migration():
    """Load the migration by file path (alembic version files are not importable)."""
    spec = importlib.util.spec_from_file_location("_migration_247", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 247 spec"
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


async def _column_exists(db_session: AsyncSession, table: str, column: str) -> bool:
    result = await db_session.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar_one_or_none() is not None


async def _drop_column_if_exists(db_session: AsyncSession) -> None:
    """Drop leads.metadata if present so upgrade() has work to do."""
    await db_session.execute(text("ALTER TABLE leads DROP COLUMN IF EXISTS metadata"))
    await db_session.flush()


async def test_upgrade_adds_leads_metadata(db_session: AsyncSession):
    """upgrade() adds metadata column to leads table."""
    _load_migration()
    await _drop_column_if_exists(db_session)
    assert not await _column_exists(db_session, "leads", "metadata")

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_exists(db_session, "leads", "metadata")


async def test_downgrade_drops_leads_metadata(db_session: AsyncSession):
    """downgrade() drops metadata column from leads table."""
    _load_migration()
    conn = await db_session.connection()
    # Ensure column exists first
    if not await _column_exists(db_session, "leads", "metadata"):
        await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_exists(db_session, "leads", "metadata")
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "downgrade"))
    assert not await _column_exists(db_session, "leads", "metadata")
