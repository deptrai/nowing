"""Integration tests for the RSS news indexer (Story 14.2a / AD-34 / AD-35)."""

from __future__ import annotations

import types

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChainLensIngestJob, Document, DocumentType, SearchSourceConnector
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import index_rss_feeds

pytestmark = [pytest.mark.integration]


@pytest.mark.usefixtures("patched_embed_texts", "patched_chunk_text")
async def test_index_rss_feeds_creates_chainlens_ingest_job(
    db_session: AsyncSession,
    db_workspace,
    db_user,
    db_rss_connector: SearchSourceConnector,
    fake_rss_articles,
    monkeypatch,
):
    """The RSS indexer ingests news Chunks to ChainLens and creates a ChainLensIngestJob (AD-35)."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(
        ingest_mod,
        "config",
        types.SimpleNamespace(
            CHAINLENS_API_URL="https://chainlens.test",
            CHAINLENS_SERVICE_TOKEN="secret",
            CHAINLENS_API_KEY="",
            CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
            CHAINLENS_INGEST_TIMEOUT_SECONDS=5.0,
            CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=1,
            CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS=0.1,
        ),
    )

    async def _fake_fetch(_url):
        return fake_rss_articles

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.fetch_feed", _fake_fetch
    )

    with respx.mock:
        respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ingestJobId": "job-news-rss-1",
                    "ingestedSourceIds": ["s1", "s2"],
                },
            )
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

    # Pattern 6: ChainLensIngestJob is persisted
    job_result = await db_session.execute(
        select(ChainLensIngestJob).where(
            ChainLensIngestJob.workspace_id == db_workspace.id,
            ChainLensIngestJob.scraper_id == "news.rss",
        )
    )
    job = job_result.scalar_one()
    assert job.status == "ok"
    assert job.child_ingest_job_ids == ["job-news-rss-1"]

    # AD-35: No local Document or Chunk rows for news
    doc_result = await db_session.execute(
        select(Document)
        .where(Document.workspace_id == db_workspace.id)
        .where(Document.document_type == DocumentType.NEWS_CONNECTOR)
    )
    docs = doc_result.scalars().all()
    assert len(docs) == 0


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

    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(
        ingest_mod,
        "config",
        types.SimpleNamespace(
            CHAINLENS_API_URL="https://chainlens.test",
            CHAINLENS_SERVICE_TOKEN="secret",
            CHAINLENS_API_KEY="",
            CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
            CHAINLENS_INGEST_TIMEOUT_SECONDS=5.0,
            CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=1,
            CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS=0.1,
        ),
    )

    with respx.mock:
        respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(
                200,
                json={"ingestJobId": "job-news-custom", "ingestedSourceIds": []},
            )
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
    """The same article link from two feeds is only ingested once."""
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

    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(
        ingest_mod,
        "config",
        types.SimpleNamespace(
            CHAINLENS_API_URL="https://chainlens.test",
            CHAINLENS_SERVICE_TOKEN="secret",
            CHAINLENS_API_KEY="",
            CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
            CHAINLENS_INGEST_TIMEOUT_SECONDS=5.0,
            CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=1,
            CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS=0.1,
        ),
    )

    with respx.mock:
        route = respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(
                200,
                json={"ingestJobId": "job-news-dedup", "ingestedSourceIds": ["s1"]},
            )
        )

        indexed, skipped, error = await index_rss_feeds(
            db_session,
            db_rss_connector.id,
            db_workspace.id,
            str(db_user.id),
        )

    assert error is None
    assert indexed == 1
    assert skipped == 0
    assert route.called
