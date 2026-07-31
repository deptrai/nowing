"""Fixtures for workspace-scoped integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = pytest.mark.integration

limiter.enabled = False


@pytest_asyncio.fixture
async def db_other_user(db_session: AsyncSession) -> User:
    """A user who is not a member of db_workspace."""
    user = User(
        id=uuid4(),
        email="other@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _add_member(
    db_session: AsyncSession,
    workspace: Workspace,
    user: User,
    role_name: str,
) -> WorkspaceMembership:
    result = await db_session.execute(
        select(WorkspaceRole).where(
            WorkspaceRole.workspace_id == workspace.id,
            WorkspaceRole.name == role_name,
        )
    )
    role = result.scalar_one()
    membership = WorkspaceMembership(
        user_id=user.id,
        workspace_id=workspace.id,
        role_id=role.id,
        is_owner=(role_name == "Owner"),
    )
    db_session.add(membership)
    await db_session.flush()
    return membership


@pytest_asyncio.fixture
async def db_editor_user(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> User:
    """An Editor member of db_workspace."""
    user = User(
        id=uuid4(),
        email="editor@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await _add_member(db_session, db_workspace, user, "Editor")
    return user


@pytest_asyncio.fixture
async def db_viewer_user(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> User:
    """A Viewer member of db_workspace."""
    user = User(
        id=uuid4(),
        email="viewer@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await _add_member(db_session, db_workspace, user, "Viewer")
    return user


async def _client_for_user(
    db_session: AsyncSession,
    user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Yield an httpx client authenticated as the given user."""

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
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as the workspace owner (db_user)."""
    async for test_client in _client_for_user(db_session, db_user):
        yield test_client


@pytest_asyncio.fixture
async def client_as_editor(
    db_session: AsyncSession,
    db_editor_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as an Editor member."""
    async for test_client in _client_for_user(db_session, db_editor_user):
        yield test_client


@pytest_asyncio.fixture
async def client_as_viewer(
    db_session: AsyncSession,
    db_viewer_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as a Viewer member."""
    async for test_client in _client_for_user(db_session, db_viewer_user):
        yield test_client


@pytest_asyncio.fixture
async def client_as_other(
    db_session: AsyncSession,
    db_other_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as a non-member user."""
    async for test_client in _client_for_user(db_session, db_other_user):
        yield test_client
