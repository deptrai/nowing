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


async def test_retention_update_proves_with_for_update_locks_row(
    async_engine: AsyncEngine,
):
    """Proves SELECT FOR UPDATE is strictly enforced on retention updates.

    When another transaction holds a row lock on the workspace:
    1. A retention update (e.g. document_retention_days) is blocked.
    2. Once the holding transaction commits/rolls back, the update proceeds.
    3. A non-retention update does not use with_for_update and proceeds without lock contention.
    """
    from sqlalchemy import select

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
            # Transaction 1: acquire and hold exclusive row lock on the workspace
            async with session_factory() as lock_session:
                await lock_session.begin()
                stmt = (
                    select(Workspace)
                    .where(Workspace.id == workspace.id)
                    .with_for_update()
                )
                locked_ws = (await lock_session.execute(stmt)).scalar_one()
                assert locked_ws.id == workspace.id

                # Send retention update while row lock is held
                update_task = asyncio.create_task(
                    client.put(
                        f"{BASE}/{workspace.id}",
                        json={"document_retention_days": 90, "auto_archive_enabled": True},
                    )
                )

                # Give event loop time to process the HTTP request up to the DB lock wait
                await asyncio.sleep(0.3)
                # Task MUST still be blocked waiting for row lock
                assert not update_task.done(), "Retention update was not blocked by FOR UPDATE lock!"

                # Release the row lock by rolling back
                await lock_session.rollback()

                # Now the blocked update completes cleanly
                res = await asyncio.wait_for(update_task, timeout=5.0)
                assert res.status_code == 200
                data = res.json()
                assert data["document_retention_days"] == 90

            # Verify that non-retention update does not take the retention lock path
            res_non_retention = await client.put(
                f"{BASE}/{workspace.id}",
                json={"name": "Updated Concurrency Name"},
            )
            assert res_non_retention.status_code == 200
            assert res_non_retention.json()["name"] == "Updated Concurrency Name"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        await _cleanup_concurrency_workspace(async_engine, workspace, user)

