"""Alembic migration 180 round-trip test (Story 6.5, AC-4).

Verifies that the migration that adds ``automation_runs.research_thread_id``
(upgrading from the 179 state) and its ``downgrade()`` are correct. The test
runs inside a single transaction so the schema changes are rolled back at
teardown, leaving the test database clean for other tests.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_MIGRATION_180_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "180_add_automation_run_research_thread.py"
)


async def _column_exists(session: AsyncSession) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'automation_runs' "
            "AND column_name = 'research_thread_id'"
        )
    )
    return result.scalar() == 1


async def _fk_exists(session: AsyncSession) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name = 'automation_runs' "
            "AND constraint_name = 'automation_runs_research_thread_id_fkey' "
            "AND constraint_type = 'FOREIGN KEY'"
        )
    )
    return result.scalar() == 1


async def _index_exists(session: AsyncSession) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename = 'automation_runs' "
            "AND indexname = 'ix_automation_runs_research_thread_id'"
        )
    )
    return result.scalar() == 1


async def _delete_rule(session: AsyncSession) -> str | None:
    result = await session.execute(
        text(
            "SELECT delete_rule FROM information_schema.referential_constraints "
            "WHERE constraint_name = 'automation_runs_research_thread_id_fkey'"
        )
    )
    return result.scalar()


async def _enum_value_exists(session: AsyncSession, value: str) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM pg_type t "
            "JOIN pg_enum e ON t.oid = e.enumtypid "
            "WHERE t.typname = 'automation_trigger_type' "
            "AND e.enumlabel = :value"
        ),
        {"value": value},
    )
    return result.scalar() == 1


def _load_migration_180():
    spec = importlib.util.spec_from_file_location(
        "_migration_180", _MIGRATION_180_PATH
    )
    assert spec and spec.loader, "could not load migration 180 spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration_upgrade(sync_conn, module) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    ctx = MigrationContext.configure(connection=sync_conn)
    with Operations.context(ctx):
        module.upgrade()


def _run_migration_downgrade(sync_conn, module) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    ctx = MigrationContext.configure(connection=sync_conn)
    with Operations.context(ctx):
        module.downgrade()


async def test_migration_180_upgrade_downgrade_roundtrip(db_session: AsyncSession):
    """The 179 -> 180 -> 179 round-trip leaves the schema as it started."""
    module = _load_migration_180()

    # Starting state (create_all-built DB): column, FK, index and enum value exist.
    assert await _column_exists(db_session)
    assert await _fk_exists(db_session)
    assert await _index_exists(db_session)
    assert await _enum_value_exists(db_session, "memory_change")

    # Simulate pre-180 by dropping the schema additions. PostgreSQL cannot
    # remove an enum value, so the value remains; upgrade() uses IF NOT EXISTS.
    await db_session.execute(
        text(
            "ALTER TABLE automation_runs "
            "DROP CONSTRAINT IF EXISTS automation_runs_research_thread_id_fkey"
        )
    )
    await db_session.execute(
        text(
            "DROP INDEX IF EXISTS ix_automation_runs_research_thread_id"
        )
    )
    await db_session.execute(
        text(
            "ALTER TABLE automation_runs "
            "DROP COLUMN IF EXISTS research_thread_id"
        )
    )

    assert not await _column_exists(db_session)
    assert not await _fk_exists(db_session)
    assert not await _index_exists(db_session)

    # Run the migration upgrade.
    conn = await db_session.connection()
    await conn.run_sync(lambda sc: _run_migration_upgrade(sc, module))

    assert await _column_exists(db_session)
    assert await _fk_exists(db_session)
    assert await _index_exists(db_session)
    assert await _enum_value_exists(db_session, "memory_change")
    assert await _delete_rule(db_session) == "SET NULL"

    # Run the migration downgrade and confirm the column/FK/index are gone.
    await conn.run_sync(lambda sc: _run_migration_downgrade(sc, module))

    assert not await _column_exists(db_session)
    assert not await _fk_exists(db_session)
    assert not await _index_exists(db_session)
