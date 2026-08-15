"""Fixtures for lead-intelligence / signal detection integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import User, Workspace, get_async_session
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]

limiter.enabled = False


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
async def seed_signal_event(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> Any:
    """Factory to create SignalEvent rows for the test workspace."""

    async def _make(**overrides: Any) -> Any:
        from app.db import SignalEvent

        defaults: dict[str, Any] = {
            "id": uuid4(),
            "workspace_id": db_workspace.id,
            "client_id": None,
            "company_name": "FPT",
            "signal_type": "funding",
            "source_url": "https://example.com/funding",
            "chunk_id": uuid4(),
            "confidence": 85.0,
            "detected_at": datetime.now(UTC),
            "processed": False,
        }
        defaults.update(overrides)
        event = SignalEvent(**defaults)
        db_session.add(event)
        await db_session.flush()
        return event

    return _make


@pytest_asyncio.fixture
async def seed_billing_event(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> Any:
    """Factory to create BillingEvent rows for the test workspace."""

    async def _make(
        signal_event_id: Any, cost_micros: int = 1000, **overrides: Any
    ) -> Any:
        from app.db import BillingEvent

        defaults: dict[str, Any] = {
            "id": uuid4(),
            "workspace_id": db_workspace.id,
            "client_id": None,
            "user_id": db_user.id,
            "event_entity_type": "signal_event",
            "event_type": "signal_scan",
            "event_id": signal_event_id,
            "cost_micros": cost_micros,
            "currency": "USD",
            "cost_basis": "estimated",
        }
        defaults.update(overrides)
        event = BillingEvent(**defaults)
        db_session.add(event)
        await db_session.flush()
        return event

    return _make
