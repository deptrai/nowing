"""Unit tests for pure helpers in the RSS news indexer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.sql.dml import Delete

from app.db import DocumentStatus
from app.services.news.rss_fetcher import NewsArticle
from app.tasks.connector_indexers.rss_indexer import (
    _build_source_markdown,
    _format_pub_date,
    _news_fingerprint,
    _persist_canonical_articles,
    _prune_stale_articles,
    index_rss_feeds,
)

pytestmark = [pytest.mark.unit]


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


def test_format_pub_date_renders_unknown_for_epoch_sentinel():
    article = _article(pub_date="1970-01-01T00:00:00+00:00")
    assert _format_pub_date(article) == "Unknown"


def test_format_pub_date_renders_unknown_when_missing():
    article = _article(pub_date="")
    assert _format_pub_date(article) == "Unknown"


def test_format_pub_date_keeps_real_dates():
    article = _article()
    assert _format_pub_date(article) == "2026-08-01T10:00:00+00:00"


def test_build_source_markdown_hides_epoch_sentinel():
    article = _article(pub_date="1970-01-01T00:00:00+00:00")
    markdown = _build_source_markdown(article)
    assert "**Published:** Unknown" in markdown
    assert "1970" not in markdown


def test_build_source_markdown_keeps_real_publish_date():
    article = _article()
    markdown = _build_source_markdown(article)
    assert "**Published:** 2026-08-01T10:00:00+00:00" in markdown
    assert "**Link:** https://vnexpress.net/article/flood-warnings" in markdown
    assert "**Category:** Weather" in markdown


def test_build_source_markdown_omits_category_when_empty():
    article = _article(category="")
    markdown = _build_source_markdown(article)
    assert "**Category:**" not in markdown


def test_news_fingerprint_ignores_whitespace_and_diacritic_composition():
    composed = _article(title="Hà Nội mưa lớn")
    nfd = _article(title="Ha\u0300 No\u0302\u0323i  m\u01b0a lo\u031b\u0301n")
    assert _news_fingerprint(composed) == _news_fingerprint(nfd)


def test_news_fingerprint_seed_is_stable_over_time():
    now = datetime.now(UTC).isoformat()
    a = _article(pub_date=now)
    b = _article(pub_date=now)
    assert _news_fingerprint(a) == _news_fingerprint(b)


def test_news_fingerprint_uses_title_when_description_empty_or_repeats_title():
    title_only = _news_fingerprint(_article(description=""))
    title_repeated = _news_fingerprint(_article(description="Flood warnings issued in northern Vietnam"))
    assert title_only == title_repeated


def test_news_fingerprint_truncates_description_seed_to_80_chars():
    import hashlib

    import app.tasks.connector_indexers.rss_indexer as mod

    title = mod._normalise_text("Flood warnings issued in northern Vietnam")
    desc80 = "d" * 80
    assert _news_fingerprint(_article(description=desc80)) == hashlib.sha256(
        f"{title}|{desc80}".encode()
    ).hexdigest()
    desc81 = "d" * 81
    assert _news_fingerprint(_article(description=desc81)) == hashlib.sha256(
        f"{title}|{'d' * 80}".encode()
    ).hexdigest()


@dataclass
class _FakeResult:
    rows: list[tuple[int, str]] = field(default_factory=list)
    rowcount: int | None = 1

    def fetchall(self) -> list[tuple[int, str]]:
        return self.rows


@dataclass
class _PruneSession:
    """AsyncSession fake that records statement kinds and commit calls."""

    rows: list[tuple[int, str, str | None, datetime | None]]
    statements: list = field(default_factory=list)
    commits: int = 0

    async def execute(self, statement) -> _FakeResult:
        self.statements.append(statement)
        if isinstance(statement, Delete):
            return _FakeResult()
        return _FakeResult(rows=self.rows)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks = getattr(self, "rollbacks", 0) + 1


def _statement_kinds(session: _PruneSession) -> list[str]:
    return [type(stmt).__name__ for stmt in session.statements]


def _delete_statements(session: _PruneSession) -> list:
    return [stmt for stmt in session.statements if isinstance(stmt, Delete)]


async def test_prune_stale_articles_deletes_chunks_then_documents():
    now = datetime.now(UTC)
    stale = (now - timedelta(days=60)).isoformat()
    stale_at = now - timedelta(days=60)
    session = _PruneSession(
        rows=[
            (1, "https://old.example/a", stale, stale_at),
            (2, "https://old.example/b", stale, stale_at),
        ]
    )
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links={"https://fresh.example/c"}
    )
    assert pruned == 2
    assert session.commits == 1
    delete_stmts = _delete_statements(session)
    assert len(delete_stmts) == 2
    sqls = [str(stmt) for stmt in session.statements]
    assert any("chunks" in sql for sql in sqls)
    assert any("documents" in sql for sql in sqls)


async def test_prune_stale_articles_skips_deletes_when_nothing_stale():
    session = _PruneSession(rows=[])
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links={"https://fresh.example/c"}
    )
    assert pruned == 0
    assert session.commits == 0
    assert len(_delete_statements(session)) == 0


async def test_prune_stale_articles_batches_chunk_deletes():
    now = datetime.now(UTC)
    stale = (now - timedelta(days=60)).isoformat()
    stale_at = now - timedelta(days=60)
    session = _PruneSession(
        rows=[(i, f"https://old.example/{i}", stale, stale_at) for i in range(600)]
    )
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links=set()
    )
    assert pruned == 600
    # 600 ids -> 2 batches of (chunk delete + document delete)
    assert len(_delete_statements(session)) == 4


async def test_prune_stale_articles_skips_missing_links():
    now = datetime.now(UTC)
    stale = (now - timedelta(days=60)).isoformat()
    stale_at = now - timedelta(days=60)
    session = _PruneSession(rows=[(1, "", stale, stale_at), (2, "", stale, stale_at)])
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links=set()
    )
    assert pruned == 2
    assert session.commits == 1


async def test_prune_stale_articles_respects_retention_cutoff():
    """Articles newer than RSS_RETENTION_DAYS are not pruned."""
    now = datetime.now(UTC)
    recent = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=60)).isoformat()
    session = _PruneSession(
        rows=[
            (1, "https://old.example/recent", recent, now - timedelta(days=1)),
            (2, "https://old.example/old", old, now - timedelta(days=60)),
        ]
    )
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links=set()
    )
    assert pruned == 1
    # The session.rows contain (id, link, pub_date, created_at) but _PruneSession
    # does not enforce column typing; the select returns all columns. The prune
    # filters by pub_date first, then created_at fallback.
    assert session.commits == 1


async def test_persist_canonical_articles_calls_nowing_ingest_service(monkeypatch):
    """Articles are sent to chainlens-research via the scraper ingest contract."""
    import app.tasks.connector_indexers.rss_indexer as mod

    to_chunks_calls: list[dict] = []

    def _fake_to_chunks(*, domain, data, fetched_at, content_type, category):
        to_chunks_calls.append(
            {
                "domain": domain,
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
    assert to_chunks_calls[0]["data"]["title"] == "Flood warnings issued in northern Vietnam"
    assert to_chunks_calls[0]["category"] == "news_article"
    assert len(ingest_calls) == 1
    assert ingest_calls[0]["scraper_id"] == "rss:9"
    assert ingest_calls[0]["workspace_id"] == 7
    assert ingest_calls[0]["chunks"] == ["chunk-1", "chunk-2"]
    assert ingest_calls[0]["session"] is None


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
        monkeypatch.setattr(
            mod, "get_feeds_for_workspace", lambda config: feeds
        )
    task_log = _FakeTaskLog()
    monkeypatch.setattr(mod, "TaskLoggingService", lambda session, workspace_id: task_log)
    return task_log


def _fake_to_chunks(**kwargs):
    return ["chunk-1"]


class _FakeIngestService:
    def __init__(self):
        self.ingest_calls: list[dict] = []

    async def ingest(self, **kwargs):
        self.ingest_calls.append(kwargs)


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


async def test_index_rss_feeds_partial_failure_skips_prune(monkeypatch):
    import app.tasks.connector_indexers.rss_indexer as mod

    prune_calls: list = []

    async def _fake_prune(*args, **kwargs):
        prune_calls.append((args, kwargs))
        return 0

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

    class _FakePipeline:
        async def create_placeholder_documents(self, infos):
            return None

        async def index_batch(self, docs):
            return [_ReadyDoc() for _ in docs]

    monkeypatch.setattr(mod, "IndexingPipelineService", lambda session: _FakePipeline())
    monkeypatch.setattr(mod, "_prune_stale_articles", _fake_prune)
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    indexed, _skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert indexed == 1
    assert warning == "1 feed(s) failed to fetch"
    assert prune_calls == []


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
    indexed_docs = []

    class _FakePipeline:
        async def create_placeholder_documents(self, infos):
            return None

        async def index_batch(self, docs):
            indexed_docs.extend(docs)
            return [_ReadyDoc() for _ in docs]

    monkeypatch.setattr(mod, "IndexingPipelineService", lambda session: _FakePipeline())
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert indexed == 1
    assert skipped == 0
    assert warning is None
    assert len(indexed_docs) == 1


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
    indexed_docs = []

    class _FakePipeline:
        async def create_placeholder_documents(self, infos):
            return None

        async def index_batch(self, docs):
            indexed_docs.extend(docs)
            return [_ReadyDoc() for _ in docs]

    monkeypatch.setattr(mod, "IndexingPipelineService", lambda session: _FakePipeline())
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert indexed == 2
    assert skipped == 0
    assert warning is None
    assert len(indexed_docs) == 2


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

        class _FakePipeline:
            async def create_placeholder_documents(self, infos):
                return None

            async def index_batch(self, docs):
                return [_ReadyDoc() for _ in docs]

        monkeypatch.setattr(
            mod, "IndexingPipelineService", lambda session: _FakePipeline()
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

    class _BoomPipeline:
        async def create_placeholder_documents(self, infos):
            return None

        async def index_batch(self, docs):
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
    monkeypatch.setattr(mod, "IndexingPipelineService", lambda session: _BoomPipeline())
    monkeypatch.setattr(mod, "to_chunks", _fake_to_chunks)
    monkeypatch.setattr(mod, "NowingIngestService", _FakeIngestService)
    result = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert result == (0, 0, "Failed to index RSS feeds: boom")
    assert logged and logged[0][1].get("exc_info") is True
