"""Fixtures for Story 26.1 lead batch and ChainLens integration tests."""

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

pytestmark = [pytest.mark.integration]

limiter.enabled = False


@pytest.fixture(autouse=True)
def _set_chainlens_service_token(monkeypatch):
    """Fix a test token so chainlens-research endpoints can authenticate."""
    from app.config import config

    monkeypatch.setattr(config, "CHAINLENS_SERVICE_TOKEN", "test-chainlens-token")


@pytest.fixture
def chainlens_headers():
    def _headers(workspace_id: int) -> dict[str, str]:
        return {
            "Authorization": "Bearer test-chainlens-token",
            "X-Workspace-Id": str(workspace_id),
        }

    return _headers


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
    """A second user who is not a member of ``db_workspace``."""
    from app.db import User

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
async def fake_embedding_model_1536(monkeypatch) -> None:
    """Force a 1536-dim fake embedding model for ChainLens chunk ingestion."""
    from app.config import config

    class _FakeModel:
        dimension = 1536

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.01] * 1536 for _ in texts]

        async def embed_text(self, text: str) -> list[float]:
            return [0.01] * 1536

    monkeypatch.setattr(config, "embedding_model_instance", _FakeModel())


@pytest.fixture
def lead_batch_payload() -> dict:
    return {
        "task_id": "task-123",
        "leads": [
            {
                "source_url": "https://example.com/lead-1",
                "company_name": "Acme Corp",
                "title": "CEO",
                "domain": "acme.com",
                "contact_name": "Alice",
                "phone": "+84908123456",
                "email": "alice@acme.com",
                "fit_score": 0.85,
                "intent_signals": ["hiring"],
                "extracted_metadata": {},
            }
        ],
    }
