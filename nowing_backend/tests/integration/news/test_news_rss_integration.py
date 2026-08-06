"""Integration tests for the RSS news indexer."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType, SearchSourceConnector
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import index_rss_feeds

pytestmark = [pytest.mark.integration]


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_index_rss_feeds_creates_news_documents(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    fake_rss_articles,
    monkeypatch,
):
    """The RSS indexer persists documents of type NEWS_CONNECTOR."""

    async def _fake_fetch(_url):
        return fake_rss_articles

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.fetch_feed", _fake_fetch
    )

    indexed, skipped, error = await index_rss_feeds(
        db_session,
        db_rss_connector.id,
        db_workspace.id,
        str(db_user.id),
    )

    assert error is None
    assert indexed == 2
    assert skipped == 0

    result = await db_session.execute(
        select(Document)
        .where(Document.workspace_id == db_workspace.id)
        .where(Document.document_type == DocumentType.NEWS_CONNECTOR)
    )
    docs = result.scalars().all()
    assert len(docs) == 2

    titles = {doc.title for doc in docs}
    assert titles == {
        "Flood warnings issued in northern Vietnam",
        "Vietnam economy grows 6.5%",
    }

    for doc in docs:
        assert doc.status == {"state": "ready"}
        assert doc.document_metadata["link"]
        assert doc.document_metadata["source"]
        assert doc.source_markdown


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_index_rss_feeds_uses_workspace_config_feeds(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    fake_rss_articles,
    monkeypatch,
):
    """Per-connector feed URL overrides are honoured."""
    db_rss_connector.config = {
        "feed_urls": ["https://custom.example/rss.xml"],
    }
    await db_session.flush()

    fetched_urls: list[str] = []

    async def _fake_fetch(url):
        fetched_urls.append(url)
        return fake_rss_articles

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.fetch_feed", _fake_fetch
    )

    await index_rss_feeds(
        db_session,
        db_rss_connector.id,
        db_workspace.id,
        str(db_user.id),
    )

    assert fetched_urls == ["https://custom.example/rss.xml"]


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_index_rss_feeds_dedup_by_article_link(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    monkeypatch,
):
    """The same article link from two feeds is only stored once."""
    duplicated = [
        NewsArticle(
            title="Same story",
            link="https://vnexpress.net/article/same",
            description="Description",
            pub_date="2024-08-06T00:00:00+00:00",
            category="News",
            source="vnexpress.net",
        ),
        NewsArticle(
            title="Same story",
            link="https://vnexpress.net/article/same",
            description="Description",
            pub_date="2024-08-06T00:00:00+00:00",
            category="News",
            source="vnexpress.net",
        ),
    ]

    async def _fake_fetch(_url):
        return duplicated

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.fetch_feed", _fake_fetch
    )

    await index_rss_feeds(
        db_session,
        db_rss_connector.id,
        db_workspace.id,
        str(db_user.id),
    )

    result = await db_session.execute(
        select(Document)
        .where(Document.workspace_id == db_workspace.id)
        .where(Document.document_type == DocumentType.NEWS_CONNECTOR)
    )
    docs = result.scalars().all()
    assert len(docs) == 1
