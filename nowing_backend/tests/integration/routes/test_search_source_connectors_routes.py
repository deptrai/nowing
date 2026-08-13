"""Integration tests for search-source-connector deletion cleanup."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    Workspace,
)
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import index_rss_feeds

pytestmark = [pytest.mark.integration]


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


async def _count_documents(session: AsyncSession, workspace_id: int) -> int:
    result = await session.execute(
        select(Document.id).where(
            Document.workspace_id == workspace_id,
            Document.document_type == DocumentType.NEWS_CONNECTOR,
        )
    )
    return len(result.scalars().all())


async def _get_entities(
    session: AsyncSession, workspace_id: int
) -> list[CanonicalEntity]:
    result = await session.execute(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == workspace_id,
            CanonicalEntity.entity_type == "news_article",
        )
    )
    return list(result.scalars().all())


async def _index(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    articles: list[NewsArticle],
    monkeypatch,
):
    async def _fake_fetch(_url):
        return articles

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.fetch_feed", _fake_fetch
    )
    return await index_rss_feeds(
        db_session,
        db_rss_connector.id,
        db_workspace.id,
        str(db_user.id),
    )


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_delete_connector_cleans_canonical_entities(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    fake_rss_articles,
    client_as_regular_user,
    monkeypatch,
):
    """Deleting a connector removes its documents AND its canonical data."""
    await _index(
        db_session,
        db_workspace,
        db_user,
        db_rss_connector,
        fake_rss_articles,
        monkeypatch,
    )
    assert len(await _get_entities(db_session, db_workspace.id)) == 2

    response = await client_as_regular_user.delete(
        f"/api/v1/search-source-connectors/{db_rss_connector.id}"
    )
    assert response.status_code == 200

    assert await _count_documents(db_session, db_workspace.id) == 0
    assert await _get_entities(db_session, db_workspace.id) == []

    sources = await db_session.scalars(
        select(CanonicalEntitySource.id).where(
            CanonicalEntitySource.workspace_id == db_workspace.id
        )
    )
    assert sources.all() == []


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_delete_connector_without_news_documents_is_noop(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    client_as_regular_user,
):
    """Deleting a connector that never indexed anything succeeds."""
    response = await client_as_regular_user.delete(
        f"/api/v1/search-source-connectors/{db_rss_connector.id}"
    )
    assert response.status_code == 200
    assert (
        await db_session.scalar(
            select(SearchSourceConnector.id).where(
                SearchSourceConnector.id == db_rss_connector.id
            )
        )
        is None
    )
