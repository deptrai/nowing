"""Platform integration test fixtures (isolated from the main integration conftest
so missing PostGIS does not break all integration tests)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import Base, User, Workspace
from tests.conftest import TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="session")
async def platform_async_engine():
    """Create a fresh engine with only the schema needed for platform tests.

    Skips the whole module if PostGIS is not available, since the global
    ``Base.metadata`` contains a ``spatial_planning_zones`` table that needs
    the ``geometry`` type.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
        connect_args={"prepared_statement_cache_size": 0},
    )

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))
        except Exception as exc:
            await conn.rollback()
            pytest.skip(f"PostGIS unavailable, skipping platform integration tests: {exc}")

        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest_asyncio.fixture
async def platform_db_session(platform_async_engine) -> AsyncSession:
    """Transaction-scoped session for platform integration tests."""
    async with platform_async_engine.connect() as conn:
        transaction = await conn.begin()
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session
        await transaction.rollback()


@pytest_asyncio.fixture
async def platform_db_user(platform_db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test-platform@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    platform_db_session.add(user)
    await platform_db_session.flush()
    return user


@pytest_asyncio.fixture
async def platform_db_workspace(
    platform_db_session: AsyncSession,
    platform_db_user: User,
) -> Workspace:
    space = Workspace(
        name="Platform Test Space",
        user_id=platform_db_user.id,
    )
    platform_db_session.add(space)
    await platform_db_session.flush()
    return space
