"""Unit tests for pure helpers in the RSS news indexer."""

from __future__ import annotations

import pytest

from app.db import DocumentStatus
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import (
    _persist_canonical_articles,
    index_rss_feeds,
)

pytestmark = [pytest.mark.unit]


class _PruneSession:
    """AsyncSession fake that records commit calls."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _article(**overrides) -> NewsArticle:
    defaults = {
        "title": "Flood warnings issued in northern Vietnam",
        "link": "https://vnexpress.net/article/flood-warnings",
        "description": "Authorities issued warnings as heavy rain flooded streets.",
        "pub_date": "2026-08-01T10:00:00+00:00",
        "category": "Weather",
        "source": "vnexpress.net",
    }
    defaults.update(overrides)
    return NewsArticle(**defaults)


async def test_persist_canonical_articles_calls_nowing_ingest_service(monkeypatch):
    """Articles are sent to chainlens-research via the scraper ingest contract."""
    import app.tasks.connector_indexers.rss_indexer as mod

    to_chunks_calls: list[dict] = []

    def _fake_to_chunks(
        *, domain, data, fetched_at, content_type, category, metadata_domain=None
    ):
        to_chunks_calls.append(
            {
                "domain": domain,
                "metadata_domain": metadata_domain,
                "data": data,
                "fetched_at": fetched_at,
                "content_type": content_type,
                "category": category,
            }
        )
        return ["chunk-1", "chunk-2"]

    ingest_calls: list[dict] = []

    class _FakeIngest:
        async def ingest(self, *, scraper_id, chunks, workspace_id, session):
            ingest_calls.append(
                {
                    "scraper_id": scraper_id,
                    "chunks": chunks,
                    "workspace_id": workspace_id,
                    "session": session,
                }
            )

    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngest)

    await _persist_canonical_articles(
        _PruneSession(rows=[]), workspace_id=7, articles=[_article()], connector_id=9
    )
    assert len(to_chunks_calls) == 1
    assert to_chunks_calls[0]["domain"] == "news"
    assert to_chunks_calls[0]["metadata_domain"] == "vnexpress.net"
    assert (
        to_chunks_calls[0]["data"]["title"]
        == "Flood warnings issued in northern Vietnam"
    )
    assert to_chunks_calls[0]["category"] == "news_article"
    assert len(ingest_calls) == 1
    assert ingest_calls[0]["scraper_id"] == "news.rss"
    assert ingest_calls[0]["workspace_id"] == 7
    assert ingest_calls[0]["chunks"] == ["chunk-1", "chunk-2"]
    assert ingest_calls[0]["session"] is not None


async def test_persist_canonical_articles_skips_ingest_when_no_chunks(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    def _fake_to_chunks(**kwargs):
        return []

    ingest_calls: list[dict] = []

    class _FakeIngest:
        async def ingest(self, **kwargs):
            ingest_calls.append(kwargs)

    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngest)

    await _persist_canonical_articles(
        _PruneSession(rows=[]), workspace_id=7, articles=[_article()], connector_id=9
    )
    assert ingest_calls == []


async def test_persist_canonical_articles_logs_chunk_failure(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    def _boom(**kwargs):
        raise ValueError("bad chunk")

    logged: list[tuple] = []

    class _FakeLogger:
        def exception(self, *args, **kwargs):
            logged.append((args, kwargs))

    monkeypatch.setattr(mod, "to_chunks", _boom)
    monkeypatch.setattr(mod, "logger", _FakeLogger())

    await _persist_canonical_articles(
        _PruneSession(rows=[]), workspace_id=7, articles=[_article()], connector_id=9
    )
    assert logged
    assert "chunk serialization failed" in logged[0][0][0]


async def test_persist_canonical_articles_logs_ingest_failure(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    def _fake_to_chunks(**kwargs):
        return ["chunk-1"]

    class _BoomIngest:
        async def ingest(self, **kwargs):
            raise RuntimeError("chainlens down")

    logged: list[tuple] = []

    class _FakeLogger:
        def exception(self, *args, **kwargs):
            logged.append((args, kwargs))

    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _BoomIngest)
    monkeypatch.setattr(mod, "logger", _FakeLogger())

    await _persist_canonical_articles(
        _PruneSession(rows=[]), workspace_id=7, articles=[_article()], connector_id=9
    )
    assert logged
    assert "chainlens ingest failed" in logged[0][0][0]


class _ReadyDoc:
    status = {"state": DocumentStatus.READY}


class _FakeConnector:
    def __init__(self, config=None):
        self.config = config or {"feeds": ["https://feed.example/rss"]}


class _FakeTaskLog:
    def __init__(self):
        self.starts = 0
        self.successes = 0
        self.failures = []
        self.success_kwargs: list[tuple] = []

    async def log_task_start(self, **kwargs):
        self.starts += 1
        return "log-1"

    async def log_task_success(self, *args, **kwargs):
        self.successes += 1
        self.success_kwargs.append((args, kwargs))

    async def log_task_failure(self, *args, **kwargs):
        self.failures.append(args)


def _patch_index_rss_deps(
    monkeypatch, *, connector=None, feeds=None, fetch_result=None
):
    import app.tasks.connector_indexers.rss_indexer as mod

    async def _fake_get_connector(session, connector_id, connector_type):
        return connector

    async def _fake_update_last_indexed(session, connector, flag):
        return None

    async def _fake_fetch_feed(url):
        if fetch_result is None:
            return []
        if callable(fetch_result):
            return fetch_result(url)
        return fetch_result

    monkeypatch.setattr(mod, "get_connector_by_id", _fake_get_connector)
    monkeypatch.setattr(mod, "update_connector_last_indexed", _fake_update_last_indexed)
    monkeypatch.setattr(mod, "fetch_feed", _fake_fetch_feed)
    if feeds is not None:
        monkeypatch.setattr(mod, "get_feeds_for_workspace", lambda config: feeds)
    task_log = _FakeTaskLog()
    monkeypatch.setattr(
        mod, "TaskLoggingService", lambda session, workspace_id: task_log
    )
    return task_log


def _fake_to_chunks(**kwargs):
    return ["chunk-1"]


class _FakeIngestService:
    def __init__(self):
        self.ingest_calls: list[dict] = []

    async def ingest(self, **kwargs):
        self.ingest_calls.append(kwargs)
        import types

        return types.SimpleNamespace(status="ok", ingest_job_id="fake-job-1")


async def test_index_rss_feeds_connector_not_found(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    log = _patch_index_rss_deps(monkeypatch, connector=None)
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=99, workspace_id=7, user_id="u1"
    )
    assert (indexed, skipped) == (0, 0)
    assert "not found" in warning
    assert log.failures


async def test_index_rss_feeds_no_feeds_configured(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    log = _patch_index_rss_deps(monkeypatch, connector=_FakeConnector(), feeds=[])
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert (indexed, skipped, warning) == (0, 0, None)
    assert log.successes == 1


async def test_index_rss_feeds_all_feeds_failed(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    def _boom(url):
        raise RuntimeError("feed down")

    log = _patch_index_rss_deps(
        monkeypatch,
        connector=_FakeConnector(),
        feeds=["https://a/x"],
        fetch_result=_boom,
    )
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert (indexed, skipped) == (0, 0)
    assert "failed" in warning
    assert log.failures


async def test_index_rss_feeds_partial_failure_indexes_successful_feed(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    def _fake_fetch_feed(url):
        if "fails" in url:
            raise RuntimeError("feed down")
        return [_article(link=f"{url}/item")]

    _patch_index_rss_deps(
        monkeypatch,
        connector=_FakeConnector(),
        feeds=["https://succeeds/x", "https://fails/x"],
        fetch_result=_fake_fetch_feed,
    )

    fake_ingest = _FakeIngestService()
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", lambda: fake_ingest)
    indexed, _skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert indexed == 1
    assert warning == "1 feed(s) failed to fetch"


async def test_index_rss_feeds_no_articles_returned(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    log = _patch_index_rss_deps(
        monkeypatch, connector=_FakeConnector(), feeds=["https://a/x"], fetch_result=[]
    )
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert (indexed, skipped, warning) == (0, 0, None)
    assert log.successes == 1


async def test_index_rss_feeds_skips_articles_without_link_or_title(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    fetched = [
        _article(title="", link="https://x/a"),
        _article(title="Has title", link=""),
        _article(),
    ]
    _patch_index_rss_deps(
        monkeypatch,
        connector=_FakeConnector(),
        feeds=["https://a/x"],
        fetch_result=fetched,
    )
    fake_ingest = _FakeIngestService()
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", lambda: fake_ingest)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert indexed == 1
    assert skipped == 0
    assert warning is None
    assert len(fake_ingest.ingest_calls) == 1
    assert len(fake_ingest.ingest_calls[0]["chunks"]) == 1


async def test_index_rss_feeds_dedup_by_article_link(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    first = _article()
    fetched = [
        first,
        _article(link=first.link),
        _article(title="Second story", link="https://vnexpress.net/article/2"),
    ]
    _patch_index_rss_deps(
        monkeypatch,
        connector=_FakeConnector(),
        feeds=["https://a/x"],
        fetch_result=fetched,
    )
    fake_ingest = _FakeIngestService()
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", lambda: fake_ingest)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert indexed == 2
    assert skipped == 0
    assert warning is None
    assert len(fake_ingest.ingest_calls) == 1
    assert len(fake_ingest.ingest_calls[0]["chunks"]) == 2


async def test_index_rss_feeds_heartbeat_call_counts(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    for count, _expected_calls in [(5, 0), (50, 1), (101, 2), (147, 2)]:
        calls: list[int] = []

        async def _heartbeat(n, calls=calls):
            calls.append(n)

        fetched = [
            _article(
                title=f"Story {i}",
                link=f"https://vnexpress.net/article/{i}",
            )
            for i in range(count)
        ]
        _patch_index_rss_deps(
            monkeypatch,
            connector=_FakeConnector(),
            feeds=["https://a/x"],
            fetch_result=fetched,
        )

        monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
        monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
        await index_rss_feeds(
            _PruneSession(rows=[]),
            connector_id=1,
            workspace_id=7,
            user_id="u1",
            on_heartbeat_callback=_heartbeat,
        )
        assert calls == [
            *range(50, count + 1, 50),
            count,
        ], f"count={count}"


async def test_index_rss_feeds_fetch_failure_logs_exc_info(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    logged: list[dict] = []

    class _FakeLogger:
        def warning(self, *args, **kwargs):
            logged.append(kwargs)

        def info(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            logged.append(kwargs)

    def _boom(url):
        raise RuntimeError("fetch fail")

    _patch_index_rss_deps(
        monkeypatch,
        connector=_FakeConnector(),
        feeds=["https://a/x"],
        fetch_result=_boom,
    )
    monkeypatch.setattr(mod, "logger", _FakeLogger())
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert logged
    assert logged[0].get("exc_info") is True


async def test_index_rss_feeds_exception_returns_failure_tuple(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    _patch_index_rss_deps(
        monkeypatch,
        connector=_FakeConnector(),
        feeds=["https://a/x"],
        fetch_result=[_article()],
    )

    async def _boom_persist(*args, **kwargs):
        raise ValueError("boom")

    logged: list[tuple] = []

    class _FakeLogger:
        def error(self, *args, **kwargs):
            logged.append((args, kwargs))

        def info(self, *args, **kwargs):
            pass

        def warning(self, *args, **kwargs):
            pass

    monkeypatch.setattr(mod, "logger", _FakeLogger())
    monkeypatch.setattr(mod, "_persist_canonical_articles", _boom_persist)
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    result = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert result == (0, 0, "Failed to index RSS feeds: boom")
    assert logged and logged[0][1].get("exc_info") is True
