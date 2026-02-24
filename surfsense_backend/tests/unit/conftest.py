from unittest.mock import AsyncMock, MagicMock

import pytest

_EMBEDDING_DIM = 4  # keep vectors tiny in tests; real model uses 768+


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()  # synchronous in real SQLAlchemy
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


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


@pytest.fixture
def mock_chunker() -> MagicMock:
    chunker = MagicMock()
    chunker.chunk = MagicMock(return_value=["chunk one", "chunk two"])
    return chunker


@pytest.fixture
def mock_code_chunker() -> MagicMock:
    chunker = MagicMock()
    chunker.chunk = MagicMock(return_value=["chunk one", "chunk two"])
    return chunker
