"""Fixtures for RSS news integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector, SearchSourceConnectorType, User, Workspace
from app.services.news.rss_fetcher import NewsArticle


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
