"""Fixtures for memory-scoped integration tests.

Provides HTTP clients that exercise the app over ASGI without a running server,
mirroring ``tests/integration/workspaces/conftest.py``:

- ``client`` — authenticated as the workspace owner (``db_user``).
- ``client_as_other`` — authenticated as ``db_other_user``, a user who is NOT a
  member of ``db_workspace`` (used to assert permission/isolation on the
  research-continuity endpoint).

Each client's session override yields the test's ``db_session`` so data created
in the test and rows read by the route share one transaction.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import User, get_async_session
from app.users import get_auth_context

pytestmark = [pytest.mark.integration, pytest.mark.memory]

limiter.enabled = False


async def _client_for_user(
    db_session: AsyncSession,
    user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Yield an httpx client authenticated as ``user``, sharing ``db_session``."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def db_other_user(db_session: AsyncSession) -> User:
    """A user who is NOT a member of ``db_workspace``."""
    user = User(
        id=uuid4(),
        email="other-memory@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as the workspace owner (db_user)."""
    async for test_client in _client_for_user(db_session, db_user):
        yield test_client


@pytest_asyncio.fixture
async def client_as_other(
    db_session: AsyncSession,
    db_other_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as a non-member user."""
    async for test_client in _client_for_user(db_session, db_other_user):
        yield test_client
