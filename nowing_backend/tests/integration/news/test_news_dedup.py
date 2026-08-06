"""Integration tests for canonical deduplication across news portals."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    Document,
    DocumentType,
)
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import index_rss_feeds

pytestmark = [pytest.mark.integration]


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_canonical_dedup_for_syndicated_article(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector,
    monkeypatch,
):
    """The same story syndicated on two portals merges into one canonical entity."""
    articles = [
        NewsArticle(
            title="Vietnam economy grows 6.5%",
            link="https://vnexpress.net/article/1",
            description="GDP expansion beat expectations, officials said.",
            pub_date="2024-08-06T00:00:00+00:00",
            category="Economy",
            source="vnexpress.net",
        ),
        NewsArticle(
            title="Vietnam economy grows 6.5%",
            link="https://tuoitre.vn/article/1",
            description="GDP expansion beat expectations, officials said.",
            pub_date="2024-08-06T00:00:00+00:00",
            category="Economy",
            source="tuoitre.vn",
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

    # Two distinct documents because the links differ.
    result = await db_session.execute(
        select(func.count())
        .select_from(Document)
        .where(Document.workspace_id == db_workspace.id)
        .where(Document.document_type == DocumentType.NEWS_CONNECTOR)
    )
    assert result.scalar() == 2

    # One canonical entity with two source portals.
    result = await db_session.execute(
        select(CanonicalEntity)
        .where(CanonicalEntity.workspace_id == db_workspace.id)
        .where(CanonicalEntity.entity_type == "news_article")
    )
    entity = result.scalars().first()
    assert entity is not None
    assert entity.source_count == 2

    result = await db_session.execute(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.canonical_entity_id == entity.id
        )
    )
    sources = result.scalars().all()
    assert len(sources) == 2
    source_names = {s.source_name for s in sources}
    assert source_names == {"vnexpress.net", "tuoitre.vn"}
