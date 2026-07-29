"""Integration tests for run-memory provenance schema (Story 3.13, T1 / AC-7).

Exercises migration ``184_add_run_memory_provenance`` against real PostgreSQL:

* ``memories.source_run_id`` is a nullable, indexed ``uuid`` and is **not** a
  foreign key to ``runs.id`` — runs are retention-cleaned after 30 days while
  the memory they produced is durable (AC-7).
* ``memories.source_id`` stays ``integer`` (never widened to hold a run UUID).
* ``runs`` carries the three durable extraction-state columns (D6).
* ``downgrade()`` removes exactly what ``upgrade()`` added.
* A memory whose ``source_run_id`` points at a deleted run still reads and
  searches without raising (dangling soft reference).

Harness note: the test DB is built by ``Base.metadata.create_all``, so the new
columns already exist. Each migration test therefore drops them first (inside
the fixture transaction, savepoint-rolled-back at teardown) and then runs the
real ``upgrade()`` with alembic's ``op`` proxy bound to the test connection —
the same technique ``test_backfill_legacy_memory.py`` uses for migration 178.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "184_add_run_memory_provenance.py"
)

_EMBEDDING_DIM = 384

MEMORY_COLUMN = "source_run_id"
RUN_COLUMNS = (
    "memory_extraction_status",
    "memory_extraction_completed_at",
    "memory_extraction_skip_reason",
)


def _load_migration():
    """Load the migration by file path (alembic version files are not importable)."""
    spec = importlib.util.spec_from_file_location("_migration_184", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 184 spec"
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


async def _drop_added_objects(db_session: AsyncSession) -> None:
    """Return the schema to its pre-184 shape so ``upgrade()`` has work to do."""
    module = _load_migration()
    await db_session.execute(
        text(f"DROP INDEX IF EXISTS {module.MEMORY_SOURCE_RUN_INDEX}")
    )
    await db_session.execute(
        text(f"DROP INDEX IF EXISTS {module.RUN_EXTRACTION_STATUS_INDEX}")
    )
    await db_session.execute(
        text(f"ALTER TABLE memories DROP COLUMN IF EXISTS {MEMORY_COLUMN}")
    )
    for column in RUN_COLUMNS:
        await db_session.execute(
            text(f"ALTER TABLE runs DROP COLUMN IF EXISTS {column}")
        )
    await db_session.flush()


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


async def _is_nullable(db_session: AsyncSession, table: str, column: str) -> str | None:
    return (
        await db_session.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
    ).scalar_one_or_none()


async def _index_exists(db_session: AsyncSession, index_name: str) -> bool:
    return (
        await db_session.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": index_name},
        )
    ).scalar_one_or_none() is not None


async def _fk_columns(db_session: AsyncSession, table: str) -> set[str]:
    """Column names on ``table`` that participate in an outbound FOREIGN KEY."""
    rows = (
        await db_session.execute(
            text(
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                " AND tc.table_schema = kcu.table_schema "
                "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = :t"
            ),
            {"t": table},
        )
    ).all()
    return {row[0] for row in rows}


# --- migration shape ------------------------------------------------------


async def test_upgrade_adds_source_run_id_as_nullable_indexed_uuid(
    db_session: AsyncSession, async_engine
):
    """AC-7: ``source_run_id`` lands as a nullable, indexed ``uuid`` column."""
    module = _load_migration()
    await _drop_added_objects(db_session)
    assert await _column_type(db_session, "memories", MEMORY_COLUMN) is None

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_type(db_session, "memories", MEMORY_COLUMN) == "uuid"
    assert await _is_nullable(db_session, "memories", MEMORY_COLUMN) == "YES"
    assert await _index_exists(db_session, module.MEMORY_SOURCE_RUN_INDEX)


async def test_upgrade_does_not_create_fk_to_runs(
    db_session: AsyncSession, async_engine
):
    """AC-7: the run reference is SOFT — a hard FK would couple memory to run retention."""
    await _drop_added_objects(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert MEMORY_COLUMN not in await _fk_columns(db_session, "memories")


async def test_upgrade_keeps_source_id_integer(db_session: AsyncSession, async_engine):
    """AC-7: ``source_id`` must stay ``integer`` (chat message ids), never widened."""
    await _drop_added_objects(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_type(db_session, "memories", "source_id") == "integer"


async def test_upgrade_adds_run_extraction_state_columns(
    db_session: AsyncSession, async_engine
):
    """D6: durable facts/zero-fact/skip state lives on ``runs``, indexed by status."""
    module = _load_migration()
    await _drop_added_objects(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert (
        await _column_type(db_session, "runs", "memory_extraction_status")
        == "character varying"
    )
    assert (
        await _column_type(db_session, "runs", "memory_extraction_completed_at")
        == "timestamp with time zone"
    )
    assert (
        await _column_type(db_session, "runs", "memory_extraction_skip_reason")
        == "character varying"
    )
    for column in RUN_COLUMNS:
        assert await _is_nullable(db_session, "runs", column) == "YES"
    assert await _index_exists(db_session, module.RUN_EXTRACTION_STATUS_INDEX)


async def test_downgrade_removes_everything_upgrade_added(
    db_session: AsyncSession, async_engine
):
    """A full downgrade is required so the revision is reversible."""
    module = _load_migration()
    await _drop_added_objects(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "downgrade"))

    assert await _column_type(db_session, "memories", MEMORY_COLUMN) is None
    assert not await _index_exists(db_session, module.MEMORY_SOURCE_RUN_INDEX)
    assert not await _index_exists(db_session, module.RUN_EXTRACTION_STATUS_INDEX)
    for column in RUN_COLUMNS:
        assert await _column_type(db_session, "runs", column) is None
    # Untouched by the downgrade.
    assert await _column_type(db_session, "memories", "source_id") == "integer"


# --- dangling soft reference ---------------------------------------------


async def test_memory_survives_run_deletion_and_stays_searchable(
    db_session: AsyncSession, db_user, db_workspace
):
    """AC-7: deleting the run leaves the memory readable/searchable, no exception."""
    from app.db import Memory, MemorySourceType, MemoryType, Run

    # Read the fixture ids up front: ``expire_all()`` below would otherwise make
    # every later attribute access an implicit lazy refresh, which raises
    # MissingGreenlet when it happens inside an argument expression.
    workspace_id = db_workspace.id
    user_id = db_user.id

    run = Run(
        workspace_id=workspace_id,
        user_id=user_id,
        capability="web.crawl",
        origin="api",
        status="success",
        output_text='{"url": "https://example.com"}',
    )
    db_session.add(run)
    await db_session.flush()
    run_id = run.id

    memory = Memory(
        workspace_id=workspace_id,
        created_by_id=user_id,
        content="Nowing ships to production on Tuesdays.",
        embedding=[0.1] * _EMBEDDING_DIM,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.SCRAPER_RUN,
        source_id=None,
        source_run_id=run_id,
    )
    db_session.add(memory)
    await db_session.flush()
    memory_id = memory.id

    # Retention cleanup deletes the run log. With no FK, this must not cascade
    # to the memory nor be blocked by it.
    await db_session.execute(text("DELETE FROM runs WHERE id = :id"), {"id": run_id})
    await db_session.flush()
    db_session.expire_all()

    reloaded = await db_session.get(Memory, memory_id)
    assert reloaded is not None
    assert reloaded.source_run_id == run_id
    assert reloaded.source_type == MemorySourceType.SCRAPER_RUN
    assert reloaded.source_id is None

    # A hybrid-search-shaped read over the dangling reference must not raise.
    rows = (
        await db_session.execute(
            text(
                "SELECT id, source_run_id FROM memories "
                "WHERE workspace_id = :ws AND source_run_id = :run"
            ),
            {"ws": workspace_id, "run": run_id},
        )
    ).all()
    assert [(memory_id, run_id)] == [(row[0], row[1]) for row in rows]


async def test_source_run_id_defaults_to_null_for_non_run_memory(
    db_session: AsyncSession, db_user, db_workspace
):
    """Chat/manual memory keeps ``source_run_id`` NULL and ``source_id`` integer."""
    from app.db import Memory, MemorySourceType, MemoryType

    memory = Memory(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        content="User prefers dark mode.",
        embedding=[0.2] * _EMBEDDING_DIM,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        source_id=4242,
    )
    db_session.add(memory)
    await db_session.flush()
    # Capture the PK BEFORE expiring: reading an expired attribute would trigger
    # a synchronous refresh outside the async greenlet.
    memory_id = memory.id
    db_session.expire_all()

    reloaded = await db_session.get(Memory, memory_id)
    assert reloaded is not None
    assert reloaded.source_run_id is None
    assert reloaded.source_id == 4242
