"""Alembic migration 235 round-trip test.

Verifies that ``235_lead_indexing_fts_and_vector.py`` adds the
``search_vector`` tsvector column, ``embedding`` vector column, GIN FTS and
pg_trgm indexes, composite B-tree indexes, and the HNSW vector index, then
removes them on downgrade.
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
    / "235_lead_indexing_fts_and_vector.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("_migration_235", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 235 spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration(sync_conn, fn_name: str) -> None:
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


async def _index_exists(db_session: AsyncSession, index: str) -> bool:
    result = await db_session.execute(
        text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :i"),
        {"i": index},
    )
    return result.scalar_one_or_none() is not None


async def _drop_column(db_session: AsyncSession, table: str, column: str) -> None:
    await db_session.execute(
        text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column} CASCADE")
    )
    await db_session.flush()


async def _drop_indexes(db_session: AsyncSession) -> None:
    for idx in [
        "ix_leads_embedding_hnsw",
        "ix_leads_search_vector_gin",
        "ix_leads_company_name_trgm",
        "ix_leads_domain_trgm",
        "ix_leads_tax_id_trgm",
        "ix_leads_ws_table_fit_score",
        "ix_leads_ws_status_fit_score",
        "ix_leads_ws_stage_created",
        "ix_leads_ws_client_fit_score",
        "ix_leads_ws_assigned_created",
    ]:
        await db_session.execute(text(f"DROP INDEX IF EXISTS {idx}"))
    await db_session.flush()


async def test_upgrade_creates_lead_indexing(db_session: AsyncSession):
    """Migration 235 adds columns, GIN / composite / HNSW indexes."""
    _load_migration()

    # Pre-clean so upgrade has work to do.
    await _drop_indexes(db_session)
    await _drop_column(db_session, "leads", "search_vector")
    await _drop_column(db_session, "leads", "embedding")

    assert not await _column_exists(db_session, "leads", "search_vector")
    assert not await _column_exists(db_session, "leads", "embedding")

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _column_exists(db_session, "leads", "search_vector")
    assert await _column_exists(db_session, "leads", "embedding")

    # Full-text + trigram GIN indexes.
    assert await _index_exists(db_session, "ix_leads_search_vector_gin")
    assert await _index_exists(db_session, "ix_leads_company_name_trgm")
    assert await _index_exists(db_session, "ix_leads_domain_trgm")
    assert await _index_exists(db_session, "ix_leads_tax_id_trgm")

    # Composite B-tree indexes for workspace-scoped filter+sort.
    assert await _index_exists(db_session, "ix_leads_ws_table_fit_score")
    assert await _index_exists(db_session, "ix_leads_ws_status_fit_score")
    assert await _index_exists(db_session, "ix_leads_ws_stage_created")
    assert await _index_exists(db_session, "ix_leads_ws_client_fit_score")
    assert await _index_exists(db_session, "ix_leads_ws_assigned_created")

    # HNSW vector index.
    assert await _index_exists(db_session, "ix_leads_embedding_hnsw")


async def test_downgrade_removes_lead_indexing(db_session: AsyncSession):
    """Migration 235 downgrade removes columns and indexes."""
    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "downgrade"))

    assert not await _column_exists(db_session, "leads", "search_vector")
    assert not await _column_exists(db_session, "leads", "embedding")

    assert not await _index_exists(db_session, "ix_leads_embedding_hnsw")
    assert not await _index_exists(db_session, "ix_leads_ws_assigned_created")
    assert not await _index_exists(db_session, "ix_leads_ws_client_fit_score")
    assert not await _index_exists(db_session, "ix_leads_ws_stage_created")
    assert not await _index_exists(db_session, "ix_leads_ws_status_fit_score")
    assert not await _index_exists(db_session, "ix_leads_ws_table_fit_score")
    assert not await _index_exists(db_session, "ix_leads_tax_id_trgm")
    assert not await _index_exists(db_session, "ix_leads_domain_trgm")
    assert not await _index_exists(db_session, "ix_leads_company_name_trgm")
    assert not await _index_exists(db_session, "ix_leads_search_vector_gin")
