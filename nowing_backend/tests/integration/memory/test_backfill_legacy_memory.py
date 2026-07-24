"""Integration tests for legacy memory backfill + migration 178 guard (Story 3-10b / G1).

G1.1 (`scripts/backfill_legacy_memory.py`): reads the pre-pivot markdown columns
``"user".memory_md`` / ``workspaces.shared_memory_md`` (raw SQL — the develop ORM
no longer maps them) and inserts structured ``memories`` rows with real (here
mocked) embeddings.

G1.2 (migration ``178_drop_legacy_memory_columns``): ``upgrade()`` refuses to
drop those columns while they still hold data with no backfilled ``memories``
row, so a deploy that forgets the backfill aborts instead of destroying memory.

Harness note: the develop ORM dropped the legacy columns, so the
``create_all``-built test DB lacks them. Each test re-adds them with raw
``ALTER TABLE`` inside the fixture transaction (savepoint-rolled-back at
teardown). The backfill and the migration are handed the test's ``db_session``
connection so their writes share that one transaction — otherwise a separate
``async_session_maker`` connection could not see the uncommitted fixture rows.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.backfill_legacy_memory import backfill

pytestmark = [pytest.mark.integration, pytest.mark.memory]


USER_MEMORY_MD = """## Preferences
- 2026-01-15: User prefers dark mode across the dashboard.
- 2026-01-16: User wants the weekly digest delivered on Mondays.
"""

WORKSPACE_MEMORY_MD = """## Team norms
- 2026-02-01: The team ships to production only on Tuesdays and Thursdays.
"""

_EMBEDDING_DIM = 384

_MIGRATION_178_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "178_drop_legacy_memory_columns.py"
)


@pytest.fixture
def patched_embeddings(monkeypatch):
    """Deterministic embeddings so the backfill needs no real model or network.

    Identical vectors make every fact a nearest-neighbour of every other, but
    ``create_memory`` only treats a hit as a duplicate when the *content* also
    matches, so distinct facts are still inserted as separate rows.
    """

    def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
        return [[0.1] * _EMBEDDING_DIM for _ in texts]

    monkeypatch.setattr(
        "app.services.memory.repository.embed_texts",
        _fake_embed_texts,
    )
    return _fake_embed_texts


async def _add_legacy_columns(db_session: AsyncSession) -> None:
    """Re-create the pre-pivot markdown columns that the develop ORM dropped."""
    await db_session.execute(
        text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS memory_md TEXT')
    )
    await db_session.execute(
        text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS shared_memory_md TEXT")
    )


async def _seed_legacy_memory(
    db_session: AsyncSession, *, user_id, user_md: str, workspace_id, workspace_md: str
) -> None:
    await _add_legacy_columns(db_session)
    await db_session.execute(
        text('UPDATE "user" SET memory_md = :md WHERE id = :id'),
        {"md": user_md, "id": user_id},
    )
    await db_session.execute(
        text("UPDATE workspaces SET shared_memory_md = :md WHERE id = :id"),
        {"md": workspace_md, "id": workspace_id},
    )
    await db_session.flush()


async def _count_memories(db_session: AsyncSession) -> int:
    return (
        await db_session.execute(text("SELECT count(*) FROM memories"))
    ).scalar_one()


def _load_migration_178():
    """Load the migration by file path (version files are not importable)."""
    spec = importlib.util.spec_from_file_location(
        "_migration_178", _MIGRATION_178_PATH
    )
    assert spec and spec.loader, "could not load migration 178 spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration_upgrade(sync_conn, module) -> None:
    """Invoke the migration's ``upgrade()`` with alembic's ``op`` proxy bound
    to ``sync_conn`` (the test transaction's connection)."""
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    ctx = MigrationContext.configure(connection=sync_conn)
    with Operations.context(ctx):
        module.upgrade()


# --- G1.1: backfill -------------------------------------------------------


async def test_backfill_creates_memories_from_legacy_columns(
    db_session, db_user, db_workspace, patched_embeddings
):
    await _seed_legacy_memory(
        db_session,
        user_id=db_user.id,
        user_md=USER_MEMORY_MD,
        workspace_id=db_workspace.id,
        workspace_md=WORKSPACE_MEMORY_MD,
    )

    created = await backfill(dry_run=False, force=False, session=db_session)

    assert created == 3  # 2 user facts + 1 workspace fact

    # Personal memory: workspace_id IS NULL, attributed to the owning user.
    user_mem = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM memories "
                "WHERE workspace_id IS NULL AND created_by_id = :uid"
            ),
            {"uid": db_user.id},
        )
    ).scalar_one()
    assert user_mem == 2

    ws_mem = (
        await db_session.execute(
            text("SELECT count(*) FROM memories WHERE workspace_id = :wid"),
            {"wid": db_workspace.id},
        )
    ).scalar_one()
    assert ws_mem == 1

    # Content actually carried across, not just row counts.
    contents = {
        row[0]
        for row in (
            await db_session.execute(text("SELECT content FROM memories"))
        ).all()
    }
    assert "User prefers dark mode across the dashboard." in contents
    assert "User wants the weekly digest delivered on Mondays." in contents
    assert (
        "The team ships to production only on Tuesdays and Thursdays." in contents
    )


async def test_backfill_is_idempotent(
    db_session, db_user, db_workspace, patched_embeddings
):
    await _seed_legacy_memory(
        db_session,
        user_id=db_user.id,
        user_md=USER_MEMORY_MD,
        workspace_id=db_workspace.id,
        workspace_md=WORKSPACE_MEMORY_MD,
    )

    first = await backfill(dry_run=False, force=False, session=db_session)
    assert first == 3
    after_first = await _count_memories(db_session)
    assert after_first == 3

    # Re-run: owners already have memories, so they are skipped (no --force).
    second = await backfill(dry_run=False, force=False, session=db_session)
    assert second == 0
    assert await _count_memories(db_session) == after_first


async def test_backfill_dry_run_reports_without_writing(
    db_session, db_user, db_workspace, patched_embeddings
):
    await _seed_legacy_memory(
        db_session,
        user_id=db_user.id,
        user_md=USER_MEMORY_MD,
        workspace_id=db_workspace.id,
        workspace_md=WORKSPACE_MEMORY_MD,
    )

    reported = await backfill(dry_run=True, force=False, session=db_session)

    assert reported == 3  # counts what WOULD be created
    assert await _count_memories(db_session) == 0  # but nothing persisted


# --- G1.2: migration 178 safety guard -------------------------------------


async def test_migration_178_guard_blocks_unmigrated_data(
    db_session, db_user, patched_embeddings
):
    """Dropping legacy columns must abort while a user's memory_md is not yet
    backfilled — the deploy-order safety net for Story 3-10b."""
    await _add_legacy_columns(db_session)
    await db_session.execute(
        text('UPDATE "user" SET memory_md = :md WHERE id = :id'),
        {"md": USER_MEMORY_MD, "id": db_user.id},
    )
    await db_session.flush()

    module = _load_migration_178()
    conn = await db_session.connection()
    # 1 user has legacy data with no backfilled `memories`; 0 workspaces do.
    with pytest.raises(RuntimeError, match=r"1 user\(s\) and 0 workspace\(s\)"):
        await conn.run_sync(lambda sc: _run_migration_upgrade(sc, module))


async def test_migration_178_drops_columns_after_backfill(
    db_session, db_user, db_workspace, patched_embeddings
):
    """Once the backfill has run, the guard is a no-op and the drop proceeds;
    the migrated `memories` rows survive."""
    await _seed_legacy_memory(
        db_session,
        user_id=db_user.id,
        user_md=USER_MEMORY_MD,
        workspace_id=db_workspace.id,
        workspace_md=WORKSPACE_MEMORY_MD,
    )
    assert await backfill(dry_run=False, force=False, session=db_session) == 3

    module = _load_migration_178()
    conn = await db_session.connection()
    await conn.run_sync(lambda sc: _run_migration_upgrade(sc, module))

    remaining_cols = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE (table_name = 'user' AND column_name = 'memory_md') "
                "OR (table_name = 'workspaces' AND column_name = 'shared_memory_md')"
            )
        )
    ).scalar_one()
    assert remaining_cols == 0
    assert await _count_memories(db_session) == 3
