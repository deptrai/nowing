"""Alembic migration 186 round-trip test (Story 9.6a, AC-1).

Verifies that ``186_add_memory_provenance_recipe.py`` adds
``memories.source_capability`` and ``memories.source_input`` and that
``downgrade()`` removes them. The test DB is built by ``Base.metadata.create_all``,
so the columns already exist; the test drops them inside the fixture transaction,
runs ``upgrade()``, asserts the columns reappear, then runs ``downgrade()`` and
asserts they vanish.
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
    / "186_add_memory_provenance_recipe.py"
)


async def _column_exists(db_session: AsyncSession, column: str) -> bool:
    result = await db_session.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'memories' AND column_name = :c"
        ),
        {"c": column},
    )
    return result.scalar_one_or_none() is not None


def _load_migration():
    """Load the migration by file path (alembic version files are not importable)."""
    spec = importlib.util.spec_from_file_location("_migration_186", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 186 spec"
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


async def _drop_added_columns(db_session: AsyncSession) -> None:
    """Return the schema to its pre-186 shape so ``upgrade()`` has work to do."""
    await db_session.execute(
        text("ALTER TABLE memories DROP COLUMN IF EXISTS source_input")
    )
    await db_session.execute(
        text("ALTER TABLE memories DROP COLUMN IF EXISTS source_capability")
    )
    await db_session.flush()


async def _column_type(db_session: AsyncSession, column: str) -> str | None:
    return (
        await db_session.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'memories' AND column_name = :c"
            ),
            {"c": column},
        )
    ).scalar_one_or_none()


async def _is_nullable(db_session: AsyncSession, column: str) -> str | None:
    return (
        await db_session.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'memories' AND column_name = :c"
            ),
            {"c": column},
        )
    ).scalar_one_or_none()


async def test_upgrade_adds_source_capability_and_input(db_session: AsyncSession):
    """AC-1: ``source_capability`` (String) and ``source_input`` (JSONB) are added."""
    _load_migration()
    await _drop_added_columns(db_session)
    assert not await _column_exists(db_session, "source_capability")
    assert not await _column_exists(db_session, "source_input")

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_exists(db_session, "source_capability")
    assert await _column_exists(db_session, "source_input")
    assert await _is_nullable(db_session, "source_capability") == "YES"
    assert await _is_nullable(db_session, "source_input") == "YES"
    assert await _column_type(db_session, "source_capability") == "character varying"
    assert await _column_type(db_session, "source_input") == "jsonb"


async def test_downgrade_removes_source_capability_and_input(db_session: AsyncSession):
    """A full downgrade removes the two columns added by 186."""
    _load_migration()
    await _drop_added_columns(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "downgrade"))

    assert not await _column_exists(db_session, "source_capability")
    assert not await _column_exists(db_session, "source_input")


_EMBEDDING_DIM = 384


async def test_upgrade_backfills_recipe_for_existing_run_derived_memory(
    db_session: AsyncSession, db_workspace, db_user
):
    """``upgrade()`` backfills recipe from ``runs`` for old run-derived memories."""
    from uuid import uuid4

    from app.db import MemorySourceType, Run
    from app.services.memory.repository import MemoryRepository

    run = Run(
        id=uuid4(),
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        thread_id=None,
        capability="reddit.scrape",
        origin="api",
        status="success",
        input={"subreddit": "r/nowing", "query": "pricing"},
        output_text='{"price": "19.99"}',
        item_count=1,
        char_count=20,
    )
    db_session.add(run)
    await db_session.flush()

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=run.id,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )
    await db_session.flush()
    assert memory.source_capability is None
    assert memory.source_input is None

    # Simulate pre-186 schema and run the migration.
    await _drop_added_columns(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    row = (
        await db_session.execute(
            text("SELECT source_capability, source_input FROM memories WHERE id = :id"),
            {"id": memory.id},
        )
    ).first()
    assert row is not None
    assert row.source_capability == "reddit.scrape"
    assert row.source_input == {"subreddit": "r/nowing", "query": "pricing"}


async def test_upgrade_backfills_with_null_run_input(
    db_session: AsyncSession, db_workspace, db_user
):
    """Backfill must set source_input=NULL when the source run has no input."""
    from uuid import uuid4

    from app.db import MemorySourceType, Run
    from app.services.memory.repository import MemoryRepository

    run = Run(
        id=uuid4(),
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        thread_id=None,
        capability="web.crawl",
        origin="api",
        status="success",
        input=None,
        output_text='{"url": "https://example.com"}',
        item_count=1,
        char_count=24,
    )
    db_session.add(run)
    await db_session.flush()

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Example domain is registered.",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=run.id,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )
    await db_session.flush()

    await _drop_added_columns(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    row = (
        await db_session.execute(
            text("SELECT source_capability, source_input FROM memories WHERE id = :id"),
            {"id": memory.id},
        )
    ).first()
    assert row is not None
    assert row.source_capability == "web.crawl"
    assert row.source_input is None
