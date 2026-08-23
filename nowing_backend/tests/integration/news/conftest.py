"""Fixtures for RSS news integration tests.

The ``client`` fixture mirrors ``tests/integration/notifications/conftest.py``:
it overrides ``get_async_session`` and ``get_auth_context`` so API calls and
seeded rows share the test's transactional ``db_session``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    Workspace,
    get_async_session,
)
from app.services.news.rss_fetcher import NewsArticle
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client riding the test transaction and a fake auth context."""
    # Lazy import to avoid a collection-time circular import in app.app.
    from app.app import app, limiter

    limiter.enabled = False

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
async def db_rss_connector(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> SearchSourceConnector:
    """Create an RSS feed connector for the test workspace."""
    connector = SearchSourceConnector(
        name="Test RSS",
        connector_type=SearchSourceConnectorType.RSS_FEED,
        is_indexable=True,
        config={},
        workspace_id=db_workspace.id,
        user_id=db_user.id,
    )
    db_session.add(connector)
    await db_session.flush()
    return connector


@pytest.fixture
def fake_rss_articles():
    """Return a small list of sample parsed articles."""
    return [
        NewsArticle(
            title="Flood warnings issued in northern Vietnam",
            link="https://vnexpress.net/article/flood-warnings",
            description="Authorities issued warnings as heavy rain flooded streets.",
            pub_date=datetime.now(UTC).isoformat(),
            category="Weather",
            source="vnexpress.net",
        ),
        NewsArticle(
            title="Vietnam economy grows 6.5%",
            link="https://tuoitre.vn/article/economy-grows",
            description="GDP expansion beat expectations in the second quarter.",
            pub_date=datetime.now(UTC).isoformat(),
            category="Economy",
            source="tuoitre.vn",
        ),
    ]


@pytest.fixture
def make_news_article():
    """Factory for sample ``NewsArticle`` rows."""

    def _make(**overrides):
        defaults = {
            "title": "Flood warnings issued in northern Vietnam",
            "link": "https://vnexpress.net/article/flood-warnings",
            "description": "Authorities issued warnings as heavy rain flooded streets.",
            "pub_date": "2024-08-06T00:00:00+00:00",
            "category": "Weather",
            "source": "vnexpress.net",
        }
        defaults.update(overrides)
        return NewsArticle(**defaults)

    return _make
