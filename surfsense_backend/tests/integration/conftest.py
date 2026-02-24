
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import Base

_EMBEDDING_DIM = 4  # keep vectors tiny; real model uses 768+

_DEFAULT_TEST_DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/surfsense_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncSession:
    # Bind the session to a connection that holds an outer transaction.
    # join_transaction_mode="create_savepoint" makes session.commit() release
    # a SAVEPOINT instead of committing the outer transaction, so the final
    # transaction.rollback() undoes everything — including commits made by the
    # service under test — leaving the DB clean for the next test.
    async with async_engine.connect() as conn:
        transaction = await conn.begin()
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session
        await transaction.rollback()


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Mocked summary."))
    return llm


@pytest.fixture
def mock_embedding_model() -> MagicMock:
    model = MagicMock()
    model.embed = MagicMock(
        side_effect=lambda texts: [[0.1] * _EMBEDDING_DIM for _ in texts]
    )
    return model
