"""Integration tests for news chunk metadata sent to chainlens-research."""

from __future__ import annotations

import importlib
import json
import types

import httpx
import pytest
import respx
from sqlalchemy import select

from app.db import ChainLensIngestJob
from app.services.chainlens.ingest import NowingIngestService
from app.services.news.rss_fetcher import NewsArticle
from app.services.scraper_chunks.schemas import ChunkMetadata, ChunkValidationError
from app.services.scraper_chunks.serializer import to_chunks

pytestmark = [pytest.mark.integration]


async def test_news_entity_chunk_metadata_ingested_to_chainlens(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """Extracted news entities and AD-34 metadata ride Chunk[] to chainlens-research."""
    _ = db_user  # the workspace is owned by this user

    # RED guards: ChunkMetadata must expose the news-specific fields.
    if "entities" not in ChunkMetadata.model_fields:
        pytest.fail("not implemented: ChunkMetadata.entities field missing")
    if "pubDate" not in ChunkMetadata.model_fields:
        pytest.fail("not implemented: ChunkMetadata.pubDate field missing")
    source_field = ChunkMetadata.model_fields.get("source")
    if source_field is not None and "nowing_scraper" in str(source_field.annotation):
        pytest.fail(
            "not implemented: ChunkMetadata.source must be a string portal name"
        )

    # RED guards: load the new entity modules, fail with "not implemented" if absent.
    try:
        news_entities_mod = importlib.import_module("app.services.news.entities")
        news_extractor_mod = importlib.import_module(
            "app.services.news.entity_extractor"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"not implemented: {exc}")

    news_entity_cls = getattr(news_entities_mod, "NewsEntity", None)
    news_extractor_cls = getattr(news_extractor_mod, "NewsEntityExtractor", None)
    if news_entity_cls is None or news_extractor_cls is None:
        pytest.fail("not implemented: NewsEntity / NewsEntityExtractor not defined")

    # Mock external chainlens-research HTTP.
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

    article = NewsArticle(
        title="Flood warnings issued in northern Vietnam",
        link="https://vnexpress.net/article/flood-warnings",
        description="Authorities issued warnings as heavy rain flooded streets.",
        pub_date="2024-08-06T00:00:00+00:00",
        category="Weather",
        source="vnexpress.net",
    )

    # Stub the LLM extraction surface so this test is deterministic.
    async def fake_extract(*_args, **_kwargs):
        return [
            news_entity_cls(
                text="<NAME>",
                type="person",
                confidence=0.95,
                surface_forms=["<NAME>"],
            ),
            news_entity_cls(
                text="Hà Nội",
                type="location",
                confidence=0.88,
                surface_forms=["Hà Nội"],
            ),
        ]

    monkeypatch.setattr(news_extractor_cls, "extract", fake_extract)
    try:
        extractor = news_extractor_cls()
    except Exception as exc:
        pytest.fail(
            f"not implemented: NewsEntityExtractor cannot be instantiated: {exc}"
        )

    raw_text = f"{article.title}\n\n{article.description}"
    try:
        extracted = await extractor.extract(raw_text, db_workspace.id, db_session)
    except Exception as exc:
        pytest.fail(f"not implemented: NewsEntityExtractor.extract failed: {exc}")

    def _entity_to_dict(entity):
        if hasattr(entity, "model_dump"):
            return entity.model_dump()
        if hasattr(entity, "dict"):
            return entity.dict()
        return {
            "text": entity.text,
            "type": entity.type,
            "confidence": entity.confidence,
            "surface_forms": entity.surface_forms,
        }

    data = {
        "title": article.title,
        "link": article.link,
        "description": article.description,
        "pubDate": article.pub_date,
        "source": article.source,
        "category": article.category,
        "entities": [_entity_to_dict(e) for e in extracted],
    }

    fetched_at = "2024-08-06T00:00:00+00:00"
    try:
        chunks = to_chunks(
            domain=article.source,
            data=data,
            fetched_at=fetched_at,
            content_type="text/markdown",
            category="news_article",
        )
    except ChunkValidationError as exc:
        pytest.fail(f"not implemented: to_chunks failed for news domain: {exc}")

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.metadata.contentType == "news", chunk.metadata.contentType
        assert chunk.metadata.domain == "vnexpress.net", chunk.metadata.domain
        assert chunk.metadata.pubDate == article.pub_date, chunk.metadata.pubDate
        assert chunk.metadata.source == article.source, chunk.metadata.source
        assert chunk.metadata.entities == data["entities"], chunk.metadata.entities
        # Person names must not leak into chunk content as-is.
        for entity in data["entities"]:
            if entity.get("type") == "person":
                for surface in entity.get("surface_forms", []):
                    assert surface not in chunk.content

    source_ids = [c.metadata.sourceId for c in chunks]

    with respx.mock:
        route = respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ingestJobId": "job-news-123",
                    "ingestedSourceIds": source_ids,
                },
            )
        )
        service = NowingIngestService()
        result = await service.ingest(
            scraper_id="news.rss",
            chunks=chunks,
            workspace_id=db_workspace.id,
            session=db_session,
        )

    assert route.called
    assert result.status == "ok"
    assert result.ingest_job_id == "job-news-123"

    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["source"] == "nowing_scraper"
    assert body["scraperId"] == "news.rss"
    assert body["workspaceId"] == db_workspace.id
    assert len(body["chunks"]) == len(chunks)
    for sent, _ in zip(body["chunks"], chunks, strict=True):
        meta = sent["metadata"]
        assert meta["contentType"] == "news"
        assert meta["domain"] == "vnexpress.net"
        assert meta["pubDate"] == article.pub_date
        assert meta["source"] == article.source
        assert meta["entities"] == data["entities"]

    # Pattern 6: the job is persisted in the same transactional session.
    job_result = await db_session.execute(
        select(ChainLensIngestJob).where(
            ChainLensIngestJob.workspace_id == db_workspace.id,
            ChainLensIngestJob.scraper_id == "news.rss",
        )
    )
    job = job_result.scalar_one()
    assert job.status == "ok"
    assert job.child_ingest_job_ids == ["job-news-123"]
    assert job.ingested_source_ids == source_ids
    assert job.noop_source_ids == []
    assert job.workspace_id == db_workspace.id
