"""Alembic migration 210 schema acceptance test (Story 22.1 / AC-1 / AD-2, AD-3, AD-5).

Verifies that ``210_add_telegram_scraper_tables.py`` creates
``telegram_channels``, ``telegram_messages``, and ``telegram_media`` with the
expected columns, composite unique constraint, HNSW vector index, GIN full-text
index, and GIN JSONB index.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "210_add_telegram_scraper_tables.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("_migration_210", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration 210 spec"
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


async def _index_definition(db_session: AsyncSession, index: str) -> str | None:
    return (
        await db_session.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = :i"
            ),
            {"i": index},
        )
    ).scalar_one_or_none()


async def _column_udt(db_session: AsyncSession, table: str, column: str) -> str | None:
    return (
        await db_session.execute(
            text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
    ).scalar_one_or_none()


async def _vector_dimension(db_session: AsyncSession, table: str, column: str) -> int | None:
    return (
        await db_session.execute(
            text(
                "SELECT a.atttypmod FROM pg_attribute a "
                "WHERE a.attrelid = :t::regclass AND a.attname = :c"
            ),
            {"t": table, "c": column},
        )
    ).scalar_one_or_none()


async def _constraint_exists(db_session: AsyncSession, constraint: str) -> bool:
    result = await db_session.execute(
        text(
            "SELECT 1 FROM pg_constraint "
            "WHERE conname = :c AND contype = 'u'"
        ),
        {"c": constraint},
    )
    return result.scalar_one_or_none() is not None


async def _drop_tables(db_session: AsyncSession) -> None:
    await db_session.execute(text("DROP TABLE IF EXISTS telegram_media CASCADE"))
    await db_session.execute(text("DROP INDEX IF EXISTS idx_telegram_msg_embedding"))
    await db_session.execute(text("DROP INDEX IF EXISTS idx_telegram_msg_text_gin"))
    await db_session.execute(text("DROP TABLE IF EXISTS telegram_messages CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS telegram_channels CASCADE"))
    await db_session.flush()


@pytest.mark.skip(reason="RED PHASE: activation pending schema acceptance gate")
async def test_upgrade_creates_telegram_schema_with_indexes(db_session: AsyncSession):
    """AC-1 / AD-2 / AD-3: migration 210 produces the correct tables/indexes."""
    _load_migration()
    await _drop_tables(db_session)

    assert not await _table_exists(db_session, "telegram_channels")
    assert not await _table_exists(db_session, "telegram_messages")
    assert not await _table_exists(db_session, "telegram_media")

    conn = await db_session.connection()
    await conn.run_sync(lambda sync_conn: _run_migration(sync_conn, "upgrade"))

    assert await _table_exists(db_session, "telegram_channels")
    assert await _table_exists(db_session, "telegram_messages")
    assert await _table_exists(db_session, "telegram_media")

    # AD-2: composite unique constraint on (channel_id, message_id)
    assert await _constraint_exists(db_session, "uq_telegram_channel_message")

    # AD-2: channel indexes
    assert await _index_exists(db_session, "idx_telegram_channels_username")
    assert await _index_exists(db_session, "idx_telegram_channels_peer_id")
    assert await _index_exists(db_session, "idx_telegram_channels_updated_at")

    # AD-2 / AD-3: message indexes
    assert await _index_exists(db_session, "idx_telegram_messages_channel_id")
    assert await _index_exists(db_session, "idx_telegram_messages_channel_date")
    assert await _index_exists(db_session, "idx_telegram_messages_entities_gin")
    assert await _index_exists(db_session, "idx_telegram_msg_intent")

    # AD-3: HNSW vector index using vector_cosine_ops
    assert await _index_exists(db_session, "idx_telegram_msg_embedding")
    embedding_def = await _index_definition(db_session, "idx_telegram_msg_embedding")
    assert embedding_def is not None
    assert "hnsw" in embedding_def.lower()
    assert "vector_cosine_ops" in embedding_def

    # AD-3: GIN full-text search index
    assert await _index_exists(db_session, "idx_telegram_msg_text_gin")
    text_gin_def = await _index_definition(db_session, "idx_telegram_msg_text_gin")
    assert text_gin_def is not None
    assert "gin" in text_gin_def.lower()
    assert "to_tsvector" in text_gin_def.lower()

    # AD-3: GIN index on raw_entities JSONB
    entities_gin_def = await _index_definition(db_session, "idx_telegram_messages_entities_gin")
    assert entities_gin_def is not None
    assert "gin" in entities_gin_def.lower()
    assert "raw_entities" in entities_gin_def

    # AD-2: JSONB raw_entities column
    assert await _column_udt(db_session, "telegram_messages", "raw_entities") == "jsonb"

    # AD-3: embedding is a pgvector vector(1536)
    assert await _column_udt(db_session, "telegram_messages", "embedding") == "vector"
    assert await _vector_dimension(db_session, "telegram_messages", "embedding") == 1536

    # AD-2: telegram_media indexes
    assert await _index_exists(db_session, "idx_telegram_media_message_id")
    assert await _index_exists(db_session, "idx_telegram_media_status")
