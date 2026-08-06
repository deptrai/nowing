"""Integration tests for searching indexed news articles."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.unified_search_service import UnifiedSearchService
from app.db import Document, DocumentType
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import index_rss_feeds

pytestmark = [pytest.mark.integration]


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_unified_search_finds_news_documents(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector,
    monkeypatch,
):
    """News articles appear in unified search results filtered by document type."""
    articles = [
        NewsArticle(
            title="Flooding in Hanoi after heavy rain",
            link="https://vnexpress.net/flooding-hanoi",
            description="Streets were submerged after a night of heavy rain.",
            pub_date="2024-08-06T00:00:00+00:00",
            category="Weather",
            source="vnexpress.net",
        ),
    ]

    async def _fake_fetch(_url):
        return articles

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.fetch_feed", _fake_fetch
    )

    await index_rss_feeds(
        db_session,
        db_rss_connector.id,
        db_workspace.id,
        str(db_user.id),
    )

    # Ensure the document is ready and content is searchable.
    result = await db_session.execute(
        select(Document)
        .where(Document.workspace_id == db_workspace.id)
        .where(Document.document_type == DocumentType.NEWS_CONNECTOR)
    )
    doc = result.scalar_one()
    assert doc.content and "Flooding" in doc.content

    monkeypatch.setattr(
        "app.canonical.services.unified_search_service.config.embedding_model_instance.embed",
        lambda _text: [0.1] * 384,
    )

    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=db_workspace.id,
        query_text="Flooding Hanoi",
        top_k=10,
        document_types=["NEWS_CONNECTOR"],
    )

    assert results
    document_results = [r for r in results if r["type"] == "document"]
    assert any(
        document_results
        and r["document"]["document"]["document_type"] == "NEWS_CONNECTOR"
        for r in document_results
    )
