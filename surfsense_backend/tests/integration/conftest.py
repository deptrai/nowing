
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import Base, SearchSpace
from app.db import User

_EMBEDDING_DIM = 1024  # must match the Vector() dimension used in DB column creation

_DEFAULT_TEST_DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/surfsense_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
        # Required for asyncpg + savepoints: disables prepared statement cache
        # to prevent "another operation is in progress" errors during savepoint rollbacks.
        connect_args={"prepared_statement_cache_size": 0},
    )

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # drop_all fails on circular FKs (new_chat_threads ↔ public_chat_snapshots).
    # DROP SCHEMA CASCADE handles this without needing topological sort.
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

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


@pytest_asyncio.fixture
async def db_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test@surfsense.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def db_search_space(db_session: AsyncSession, db_user: User) -> SearchSpace:
    space = SearchSpace(
        name="Test Space",
        user_id=db_user.id,
    )
    db_session.add(space)
    await db_session.flush()
    return space


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Mocked summary."))
    return llm


@pytest.fixture
def patched_generate_summary(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value=("Mocked summary.", [0.1] * _EMBEDDING_DIM))
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.generate_document_summary",
        mock,
    )
    return mock


@pytest.fixture
def patched_create_chunks(monkeypatch) -> MagicMock:
    from app.db import Chunk

    chunk = Chunk(content="Test chunk content.", embedding=[0.1] * _EMBEDDING_DIM)
    mock = AsyncMock(return_value=[chunk])
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.create_document_chunks",
        mock,
    )
    return mock


@pytest.fixture
def patched_embedding_model(monkeypatch) -> MagicMock:
    from app.config import config

    model = MagicMock()
    model.embed = MagicMock(return_value=[0.1] * _EMBEDDING_DIM)
    monkeypatch.setattr(config, "embedding_model_instance", model)
    return model
