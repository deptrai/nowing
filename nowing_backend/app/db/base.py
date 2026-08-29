"""SQLAlchemy Base, engine, session factory, and database helpers."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import anyio
from sqlalchemy import TIMESTAMP, Column, Integer, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, declared_attr

from app.config import config

logger = logging.getLogger(__name__)

DATABASE_URL = config.DATABASE_URL


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    @declared_attr
    def created_at(cls):  # noqa: N805
        return Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
            server_default=text("now()"),
            index=True,
        )


class BaseModel(Base):
    __abstract__ = True
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)


def _build_connect_args() -> dict:
    """Build driver connect_args, including a protective idle-in-transaction
    timeout for asyncpg connections.
    """
    connect_args: dict = {}
    idle_ms = config.DB_IDLE_IN_TX_TIMEOUT_MS
    if idle_ms and idle_ms > 0 and DATABASE_URL and "asyncpg" in DATABASE_URL:
        connect_args["server_settings"] = {
            "idle_in_transaction_session_timeout": str(idle_ms)
        }
    return connect_args


engine = create_async_engine(
    DATABASE_URL,
    pool_size=30,
    max_overflow=150,
    pool_recycle=1800,
    pool_pre_ping=True,
    pool_timeout=30,
    connect_args=_build_connect_args(),
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def shielded_async_session():
    """Cancellation-safe async session context manager."""
    session = async_session_maker()
    try:
        yield session
    finally:
        with anyio.CancelScope(shield=True):
            await session.close()


# (index_name, table, CREATE statement). Built with CONCURRENTLY.
_INDEX_DEFINITIONS: list[tuple[str, str, str]] = [
    (
        "document_vector_index",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS document_vector_index ON documents USING hnsw (embedding public.vector_cosine_ops)",
    ),
    (
        "document_search_index",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS document_search_index ON documents USING gin (to_tsvector('english', content))",
    ),
    (
        "chucks_vector_index",
        "chunks",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS chucks_vector_index ON chunks USING hnsw (embedding public.vector_cosine_ops)",
    ),
    (
        "chucks_search_index",
        "chunks",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS chucks_search_index ON chunks USING gin (to_tsvector('english', content))",
    ),
    (
        "idx_documents_title_trgm",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_title_trgm ON documents USING gin (title gin_trgm_ops)",
    ),
    (
        "idx_documents_workspace_id",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_workspace_id ON documents (workspace_id)",
    ),
    (
        "idx_documents_workspace_updated",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_workspace_updated ON documents (workspace_id, updated_at DESC NULLS LAST) INCLUDE (id, title, document_type)",
    ),
]


async def _drop_invalid_index(conn, name: str) -> None:
    """Drop a leftover invalid index so it can be rebuilt."""
    result = await conn.execute(
        text("SELECT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:n)"),
        {"n": name},
    )
    row = result.first()
    if row is not None and row[0] is False:
        logger.warning(
            "[startup] dropping invalid leftover index %s before rebuild", name
        )
        await conn.execute(text(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"'))


async def setup_indexes() -> None:
    """Ensure search/vector indexes exist without ever blocking startup."""
    lock_timeout_ms = int(config.DB_DDL_LOCK_TIMEOUT_MS)
    async with engine.connect() as base_conn:
        conn = await base_conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"SET lock_timeout = {lock_timeout_ms}"))
        for name, table, ddl in _INDEX_DEFINITIONS:
            try:
                await _drop_invalid_index(conn, name)
                await conn.execute(text(ddl))
            except Exception as exc:
                logger.warning(
                    "[startup] index %s on %s not ready (%s: %s); "
                    "will retry on next boot",
                    name,
                    table,
                    exc.__class__.__name__,
                    exc,
                )


async def create_db_and_tables():
    if not config.DB_BOOTSTRAP_ON_STARTUP:
        logger.info(
            "[startup] DB bootstrap skipped (DB_BOOTSTRAP_ON_STARTUP=FALSE); "
            "schema/indexes are expected to be managed by migrations"
        )
        return

    lock_timeout_ms = int(config.DB_DDL_LOCK_TIMEOUT_MS)
    async with engine.begin() as conn:
        await conn.execute(text(f"SET LOCAL lock_timeout = {lock_timeout_ms}"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        try:
            await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.warning(
                "[startup] Base.metadata.create_all encountered error (managed by Alembic): %s",
                exc,
            )
        from app.zero_publication import ensure_publication

        try:
            await conn.run_sync(ensure_publication)
        except Exception as exc:
            logger.warning("[startup] ensure_publication encountered error: %s", exc)
    await setup_indexes()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
