"""Fixtures for chainlens.research fallback integration tests."""

from __future__ import annotations

import importlib
from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    Chunk,
    Document,
    DocumentType,
    User,
    Workspace,
    get_async_session,
)
from app.routes.workspaces_routes import create_default_roles_and_membership
from app.users import get_auth_context

_rest_module = importlib.import_module("app.capabilities.core.access.rest")

pytestmark = pytest.mark.integration

limiter.enabled = False


class _DbSessionContext:
    """Make db_session usable by code that opens a fresh ``async_session_maker()``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args) -> None:
        return None


def _use_db_session_for_async_session_maker(session: AsyncSession):
    """Patch the REST recorder's session factory so record_run sees the test txn."""
    original = _rest_module.async_session_maker
    _rest_module.async_session_maker = lambda: _DbSessionContext(session)
    return original


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

    original_async_session_maker = _use_db_session_for_async_session_maker(db_session)

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
        _rest_module.async_session_maker = original_async_session_maker


@pytest_asyncio.fixture
async def client_as_other(
    db_session: AsyncSession,
    db_other_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as a non-member user."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_other_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    original_async_session_maker = _use_db_session_for_async_session_maker(db_session)

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
        _rest_module.async_session_maker = original_async_session_maker


@pytest_asyncio.fixture
async def db_other_user(db_session: AsyncSession) -> User:
    """A second user who is not a member of db_workspace."""
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


@pytest_asyncio.fixture
async def db_other_workspace(
    db_session: AsyncSession, db_other_user: User
) -> Workspace:
    """A second workspace owned by db_other_user."""
    space = Workspace(name="Other Space", user_id=db_other_user.id)
    db_session.add(space)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, space.id, db_other_user.id)
    await db_session.flush()
    return space


@pytest_asyncio.fixture
async def seed_research_document(db_session: AsyncSession):
    """Factory to create a Document + Chunk for KB fallback tests."""

    async def _make(
        workspace_id: int,
        *,
        title: str = "Research Doc",
        content: str = "Fallback evidence content.",
        keyword: str = "evidence",
        embedding: list[float] | None = None,
    ) -> Document:
        from app.config import config

        if embedding is None:
            embedding = [0.0] * config.embedding_model_instance.dimension

        document = Document(
            title=title,
            document_type=DocumentType.FILE,
            content=f"{keyword} {content}",
            content_hash=uuid4().hex,
            workspace_id=workspace_id,
            status={"state": "ready"},
            embedding=embedding,
        )
        db_session.add(document)
        await db_session.flush()

        db_session.add(
            Chunk(
                content=f"{keyword} {content}",
                document_id=document.id,
                position=0,
                embedding=embedding,
            )
        )
        await db_session.flush()
        return document

    return _make
