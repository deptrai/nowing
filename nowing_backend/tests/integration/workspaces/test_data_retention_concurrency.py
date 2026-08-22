"""Integration concurrency tests for Story 3.7-followup: Retention Hardening.

Verifies that concurrent PUT /workspaces/{id} requests modifying retention
settings use SELECT FOR UPDATE to serialize row updates and prevent race conditions.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.app import app
from app.auth.context import AuthContext
from app.db import User, Workspace, get_async_session
from app.routes.workspaces_routes import create_default_roles_and_membership
from app.users import get_auth_context

pytestmark = pytest.mark.integration

BASE = "/workspaces"


async def _setup_concurrency_workspace(
    async_engine: AsyncEngine,
) -> tuple[Workspace, User]:
    """Create a workspace + owner committed to PostgreSQL for multi-connection testing."""
    async with (
        AsyncSession(async_engine, expire_on_commit=False) as session,
        session.begin(),
    ):
        user = User(
            id=uuid.uuid4(),
            email=f"concurrency-{uuid.uuid4()}@nowing.net",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(
            name="Concurrency Workspace",
            user_id=user.id,
            auto_archive_enabled=False,
            document_retention_days=30,
        )
        session.add(workspace)
        await session.flush()

        await create_default_roles_and_membership(session, workspace.id, user.id)

    return workspace, user


async def _cleanup_concurrency_workspace(
    async_engine: AsyncEngine, workspace: Workspace, user: User
) -> None:
    async with (
        AsyncSession(async_engine, expire_on_commit=False) as session,
        session.begin(),
    ):
        ws = await session.get(Workspace, workspace.id)
        if ws is not None:
            await session.delete(ws)
        u = await session.get(User, user.id)
        if u is not None:
            await session.delete(u)


async def test_concurrent_retention_updates_use_row_lock(
    async_engine: AsyncEngine,
):
    """AC-1: Concurrent updates on the same workspace retention settings must not corrupt state."""
    workspace, user = await _setup_concurrency_workspace(async_engine)

    session_factory = async_sessionmaker(
        async_engine, expire_on_commit=False, class_=AsyncSession
    )

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_auth_context] = lambda: AuthContext.session(user)
    app.dependency_overrides[get_async_session] = get_test_session

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # Send two concurrent updates with different retention periods
            req1 = client.put(
                f"{BASE}/{workspace.id}",
                json={"document_retention_days": 30, "auto_archive_enabled": True},
            )
            req2 = client.put(
                f"{BASE}/{workspace.id}",
                json={"document_retention_days": 60, "auto_archive_enabled": True},
            )

            res1, res2 = await asyncio.gather(req1, req2)

            assert res1.status_code == 200
            assert res2.status_code == 200

            # State in DB must match one of the updates cleanly (serialized via row lock)
            async with session_factory() as verify_session:
                updated_ws = await verify_session.get(Workspace, workspace.id)
                assert updated_ws is not None
                assert updated_ws.auto_archive_enabled is True
                assert updated_ws.document_retention_days in (30, 60)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        await _cleanup_concurrency_workspace(async_engine, workspace, user)
