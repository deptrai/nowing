"""Alembic migration 246 round-trip test (Story 41.1).

Verifies that ``246_add_webset_campaigns_table.py`` creates the
``webset_campaigns`` table with the expected indexes, and that
``downgrade()`` removes it. The test DB is built by
``Base.metadata.create_all``, so the table already exists; the test drops it
inside the fixture transaction, runs ``upgrade()``, asserts the table and
indexes reappear, then runs ``downgrade()`` and asserts it vanishes.
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
    / "246_add_webset_campaigns_table.py"
)


def _load_migration():
    """Load the migration by file path (alembic version files are not importable)."""
    spec = importlib.util.spec_from_file_location("_migration_246", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 246 spec"
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


async def _drop_table(db_session: AsyncSession) -> None:
    """Return the schema to its pre-246 shape so ``upgrade()`` has work to do."""
    await db_session.execute(text("DROP TABLE IF EXISTS webset_campaigns CASCADE"))
    await db_session.flush()


async def test_upgrade_creates_webset_campaigns(db_session: AsyncSession):
    """upgrade() creates webset_campaigns with the three declared indexes."""
    _load_migration()
    await _drop_table(db_session)
    assert not await _table_exists(db_session, "webset_campaigns")

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _table_exists(db_session, "webset_campaigns")
    assert await _index_exists(db_session, "ix_webset_campaigns_webset_id")
    assert await _index_exists(db_session, "ix_webset_campaigns_workspace_id")
    assert await _index_exists(db_session, "ix_webset_campaigns_campaign_id")


async def test_downgrade_drops_webset_campaigns(db_session: AsyncSession):
    """A full downgrade removes the table added by 246."""
    _load_migration()
    await _drop_table(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "downgrade"))

    assert not await _table_exists(db_session, "webset_campaigns")
