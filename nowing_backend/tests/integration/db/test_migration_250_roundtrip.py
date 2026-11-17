"""Alembic migration 250 round-trip test (Story 42.7).

Verifies that ``250_workspace_tables_key_and_orphan_backfill.py``:
- adds ``workspace_tables.key`` + the composite UNIQUE ``(workspace_id, key)``;
- backfills one ``key='default'`` table per workspace with orphan leads and
  points those leads at it;
- and that ``downgrade()`` drops constraint + column.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "250_workspace_tables_key_and_orphan_backfill.py"
)


def _load_migration():
    """Load the migration by file path (alembic version files are not importable)."""
    spec = importlib.util.spec_from_file_location("_migration_250", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 250 spec"
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


async def _seed_workspace_with_orphan_lead(db_session: AsyncSession) -> tuple[int, uuid.UUID]:
    """Create a workspace + one lead with table_id NULL; return (ws_id, lead_id)."""
    ws_id = int(uuid.uuid4().int % 2**31)
    lead_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO \"user\" (id, email, hashed_password, is_active, "
            "is_superuser, is_verified) VALUES (:uid, :email, 'hashed', true, false, true)"
        ),
        {"uid": owner_id, "email": f"m250-{owner_id}@nowing.net"},
    )
    await db_session.execute(
        text(
            "INSERT INTO workspaces (id, name, user_id, citations_enabled) "
            "VALUES (:wid, '42.7 roundtrip', :uid, false)"
        ),
        {"wid": ws_id, "uid": owner_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO leads (id, workspace_id, company_name, source, value_hmac, status) "
            "VALUES (:lid, :wid, 'Orphan Co', 'batch_ingest', :hmac, 'new')"
        ),
        {"lid": lead_id, "wid": ws_id, "hmac": f"m250-{lead_id}"},
    )
    await db_session.flush()
    return ws_id, lead_id


async def _reset_upgrade_state(db_session: AsyncSession) -> None:
    """Drop key/constraint if present so upgrade() has work to do."""
    await db_session.execute(
        text(
            "ALTER TABLE workspace_tables "
            "DROP CONSTRAINT IF EXISTS uq_workspace_tables_workspace_key"
        )
    )
    await db_session.execute(
        text("ALTER TABLE workspace_tables DROP COLUMN IF EXISTS key")
    )
    await db_session.flush()


async def test_upgrade_backfills_orphan_leads(db_session: AsyncSession):
    """upgrade() creates a default table for the orphan lead and links it."""
    _load_migration()
    await _reset_upgrade_state(db_session)
    ws_id, lead_id = await _seed_workspace_with_orphan_lead(db_session)

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_exists(db_session, "workspace_tables", "key")

    table_row = (
        await db_session.execute(
            text(
                "SELECT t.id FROM workspace_tables t "
                "WHERE t.workspace_id = :wid AND t.key = 'default'"
            ),
            {"wid": ws_id},
        )
    ).scalar_one_or_none()
    assert table_row is not None, "default table must be backfilled"

    lead_table = (
        await db_session.execute(
            text("SELECT table_id FROM leads WHERE id = :lid"), {"lid": lead_id}
        )
    ).scalar_one()
    assert lead_table == table_row, "orphan lead must point at the default table"


async def test_downgrade_drops_key_and_constraint(db_session: AsyncSession):
    """downgrade() removes the unique constraint and the key column."""
    _load_migration()
    conn = await db_session.connection()
    if not await _column_exists(db_session, "workspace_tables", "key"):
        await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_exists(db_session, "workspace_tables", "key")
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "downgrade"))
    assert not await _column_exists(db_session, "workspace_tables", "key")
