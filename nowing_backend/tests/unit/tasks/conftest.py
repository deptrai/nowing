"""Unit-test fixtures for tasks package.

Override the root ``async_session`` fixture with a lightweight AsyncMock so that
tests which pass a session to the indexer (but mock all actual DB calls) never
attempt to create a real SQLite schema — which would fail because
``app/db.py`` contains PostgreSQL-specific ``server_default`` expressions such as
``'PENDING'::pagepurchasestatus`` that SQLite cannot parse.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def async_session():
    """Provide a mock AsyncSession for unit tests.

    All indexer unit tests mock their own DB queries; the session itself is only
    passed down as a dependency and never executed directly.  Using a real SQLite
    engine fails because the ORM metadata contains PostgreSQL-specific DDL that
    SQLite cannot parse (e.g. ``'PENDING'::pagepurchasestatus``).
    """
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session
