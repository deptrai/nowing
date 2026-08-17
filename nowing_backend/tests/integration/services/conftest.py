"""Shared fixtures for service-level integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import PersonalAccessToken, User, Workspace, get_async_session
from app.users import get_auth_context

pytestmark = pytest.mark.integration

limiter.enabled = False


class _AsyncSessionWrapper:
    """Makes the transactional ``db_session`` fixture usable as a
    ``billable_call`` session factory while isolating savepoint rollbacks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._nested: Any = None

    async def __aenter__(self) -> AsyncSession:
        self._nested = self._session.begin_nested()
        await self._nested.__aenter__()
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        if self._nested is not None:
            with suppress(Exception):
                await self._nested.__aexit__(*exc)


@pytest.fixture
def billable_session_factory(db_session: AsyncSession) -> Any:
    """Return an async context manager that yields the test db_session.

    ``billable_call`` defaults to ``shielded_async_session``, which opens a
    separate connection and commits outside the test transaction. This wrapper
    forces ``billable_call`` to use the transactional fixture so the outer
    rollback cleans up credit debits / TokenUsage rows automatically.
    """
    return lambda: _AsyncSessionWrapper(db_session)


@pytest.fixture
def fake_redis() -> AsyncMock:
    """Async Redis double with the commands HybridLLMRouter uses for quota."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="0")
    redis.incr = AsyncMock(return_value=1)
    redis.incrby = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as the workspace owner (db_user)."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_user)

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
async def pat_workspace_client(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """PAT-authenticated client scoped to db_workspace."""
    pat = PersonalAccessToken(
        user_id=db_user.id,
        user=db_user,
        token_hash="0" * 64,
        token_prefix="nw_pat_test",
        label="Test PAT",
        workspace_id=db_workspace.id,
    )
    auth = AuthContext.pat_auth(db_user, pat)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return auth

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
