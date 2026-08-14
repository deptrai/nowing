"""Integration tests for RSS retention pruning and canonical cleanup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    CanonicalMergeHistory,
    Document,
    DocumentType,
    SearchSourceConnector,
)
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import index_rss_feeds

pytestmark = [pytest.mark.integration]


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
async def test_prune_stale_articles_removes_docs_and_canonical(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    fake_rss_articles,
    monkeypatch,
):
    """Articles that leave the feed's rolling window are pruned along with
    their canonical provenance and orphaned entities."""
    await _index(
        db_session,
        db_workspace,
        db_user,
        db_rss_connector,
        fake_rss_articles,
        monkeypatch,
    )
    assert await _count_documents(db_session, db_workspace.id) == 2
    assert len(await _get_entities(db_session, db_workspace.id)) == 2

    # Age the first article so it falls outside the retention window.
    stale_link = fake_rss_articles[0].link
    stale_doc = await db_session.scalar(
        select(Document).where(
            Document.document_metadata["link"].as_string() == stale_link
        )
    )
    stale_pub_date = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    stale_doc.document_metadata["pubDate"] = stale_pub_date
    stale_doc.created_at = datetime.now(UTC) - timedelta(days=40)
    flag_modified(stale_doc, "document_metadata")
    await db_session.commit()

    # The next poll only sees the second article; the stale one must go.
    await _index(
        db_session,
        db_workspace,
        db_user,
        db_rss_connector,
        [fake_rss_articles[1]],
        monkeypatch,
    )

    assert await _count_documents(db_session, db_workspace.id) == 1
    docs = (
        await db_session.scalars(
            select(Document.document_metadata["link"].as_string()).where(
                Document.workspace_id == db_workspace.id,
                Document.document_type == DocumentType.NEWS_CONNECTOR,
            )
        )
    ).all()
    assert list(docs) == [fake_rss_articles[1].link]

    entities = await _get_entities(db_session, db_workspace.id)
    assert len(entities) == 1
    entity = entities[0]
    assert fake_rss_articles[1].title in entity.canonical_title

    sources = await db_session.scalars(
        select(CanonicalEntitySource.id).where(
            CanonicalEntitySource.workspace_id == db_workspace.id
        )
    )
    assert len(sources.all()) == 1


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_reindex_unchanged_articles_does_not_bump_version(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    fake_rss_articles,
    monkeypatch,
):
    """Re-polling unchanged articles must not churn version/merge history."""
    await _index(
        db_session,
        db_workspace,
        db_user,
        db_rss_connector,
        fake_rss_articles,
        monkeypatch,
    )
    await _index(
        db_session,
        db_workspace,
        db_user,
        db_rss_connector,
        fake_rss_articles,
        monkeypatch,
    )

    entities = await _get_entities(db_session, db_workspace.id)
    assert len(entities) == 2
    for entity in entities:
        assert entity.version == 1

    history = await db_session.scalars(
        select(CanonicalMergeHistory).where(
            CanonicalMergeHistory.workspace_id == db_workspace.id
        )
    )
    operations = [h.operation for h in history.all()]
    assert operations == ["create", "create"]


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_content_change_still_bumps_version(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    fake_rss_articles,
    monkeypatch,
):
    """A genuinely changed article still records a merge."""
    await _index(
        db_session,
        db_workspace,
        db_user,
        db_rss_connector,
        fake_rss_articles,
        monkeypatch,
    )

    changed = [
        NewsArticle(
            title=fake_rss_articles[0].title,
            link=fake_rss_articles[0].link,
            description=fake_rss_articles[0].description,
            pub_date=fake_rss_articles[0].pub_date,
            category="Environment",
            source=fake_rss_articles[0].source,
        ),
        fake_rss_articles[1],
    ]
    await _index(
        db_session, db_workspace, db_user, db_rss_connector, changed, monkeypatch
    )

    entities = await _get_entities(db_session, db_workspace.id)
    versions = sorted(e.version for e in entities)
    assert versions == [1, 2]

    history = await db_session.scalars(
        select(CanonicalMergeHistory).where(
            CanonicalMergeHistory.workspace_id == db_workspace.id
        )
    )
    operations = [h.operation for h in history.all()]
    assert sorted(operations) == ["create", "create", "merge"]
