"""Unit tests for pure helpers in the RSS news indexer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

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
    _source_name_for_canonical,
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
    """The 1970-01-01 sentinel never leaks into display text."""
    article = _article(pub_date="1970-01-01T00:00:00+00:00")
    assert _format_pub_date(article) == "Unknown"


def test_format_pub_date_renders_unknown_when_missing():
    article = _article(pub_date="")
    assert _format_pub_date(article) == "Unknown"


def test_format_pub_date_keeps_real_dates():
    article = _article(pub_date="2026-08-01T10:00:00+00:00")
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


def test_fingerprint_ignores_whitespace_and_diacritic_composition():
    composed = _article(title="Hà Nội mưa lớn")
    nfd = _article(title="Ha\u0300 No\u0302\u0323i  m\u01b0a lo\u031b\u0301n")
    assert _news_fingerprint(composed) == _news_fingerprint(nfd)


def test_source_name_uses_hostname_without_www():
    article = _article(link="https://www.vnexpress.net/article/x")
    assert _source_name_for_canonical(article) == "vnexpress.net"


def test_source_name_falls_back_to_channel_on_invalid_url():
    article = _article(link="not a url", source="vnexpress.net")
    assert _source_name_for_canonical(article) == "vnexpress.net"


def test_fingerprint_seed_is_stable_over_time():
    """Same title+description always produces the same fingerprint."""
    now = datetime.now(UTC).isoformat()
    a = _article(pub_date=now)
    b = _article(pub_date=now)
    assert _news_fingerprint(a) == _news_fingerprint(b)


@dataclass
class _FakeResult:
    rows: list[tuple[int, str]] = field(default_factory=list)
    rowcount: int | None = 1

    def fetchall(self) -> list[tuple[int, str]]:
        return self.rows


@dataclass
class _PruneSession:
    """AsyncSession fake that records statement kinds and commit calls."""

    rows: list[tuple[int, str]]
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


async def test_prune_stale_articles_deletes_chunks_docs_and_canonical():
    session = _PruneSession(
        rows=[(1, "https://old.example/a"), (2, "https://old.example/b")]
    )
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links={"https://fresh.example/c"}
    )
    assert pruned == 2
    assert session.commits == 1
    kinds = _statement_kinds(session)
    # select -> chunk delete -> document delete -> source delete -> entity delete
    assert kinds.count("Delete") == 4
    assert any("Select" in k for k in kinds)
    sqls = [str(stmt) for stmt in session.statements]
    assert any("chunks" in sql for sql in sqls)
    assert any("documents" in sql for sql in sqls)
    assert any("canonical_entity_sources" in sql for sql in sqls)
    assert any("canonical_entities" in sql for sql in sqls)


async def test_prune_stale_articles_skips_deletes_when_nothing_stale():
    session = _PruneSession(rows=[])
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links={"https://fresh.example/c"}
    )
    assert pruned == 0
    assert session.commits == 0
    assert len(session.statements) == 1  # only the select


async def test_prune_stale_articles_batches_chunk_deletes():
    session = _PruneSession(rows=[(i, f"https://old.example/{i}") for i in range(600)])
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links=set()
    )
    assert pruned == 600
    kinds = _statement_kinds(session)
    assert kinds.count("Delete") == 6  # 2 chunk + docs + 2 source batches + entities


async def test_prune_stale_articles_skips_missing_links():
    session = _PruneSession(rows=[(1, ""), (2, "")])
    pruned = await _prune_stale_articles(
        session, connector_id=9, workspace_id=7, seen_links=set()
    )
    assert pruned == 2
    assert session.commits == 1


async def test_persist_canonical_articles_forwards_upsert_kwargs(monkeypatch):
    """The churn-safe upsert path builds the right canonical payload."""
    calls: list[dict] = []

    async def _fake_upsert(session, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.upsert_canonical_entity",
        _fake_upsert,
    )
    await _persist_canonical_articles(
        _PruneSession(rows=[]), workspace_id=7, articles=[_article()], connector_id=9
    )
    assert len(calls) == 1
    kw = calls[0]
    assert kw["workspace_id"] == 7
    assert kw["entity_type"] == "news_article"
    assert kw["source_record_id"] == "https://vnexpress.net/article/flood-warnings"
    assert kw["merge_method"] == "rss_fingerprint"
    assert kw["actor"] == "rss-connector:9"
    assert kw["confidence_score"] == 0.9
    assert kw["fingerprint"] == _news_fingerprint(_article())
    assert kw["source_fingerprint"] == kw["fingerprint"]
    assert kw["search_text"].endswith("Weather")
    assert kw["data"]["category"] == "Weather"
    assert kw["source_snapshot"]["link"] == kw["data"]["link"]


async def test_persist_canonical_articles_omits_empty_category(monkeypatch):
    calls: list[dict] = []

    async def _fake_upsert(session, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.upsert_canonical_entity",
        _fake_upsert,
    )
    await _persist_canonical_articles(
        _PruneSession(rows=[]),
        workspace_id=7,
        articles=[_article(category="")],
        connector_id=9,
    )
    assert len(calls) == 1
    assert calls[0]["search_text"] == (
        "Flood warnings issued in northern Vietnam "
        "Authorities issued warnings as heavy rain flooded streets."
    )


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

    async def log_task_start(self, **kwargs):
        self.starts += 1
        return "log-1"

    async def log_task_success(self, *args, **kwargs):
        self.successes += 1

    async def log_task_failure(self, *args, **kwargs):
        self.failures.append(args)


def _patch_index_rss_deps(
    monkeypatch, *, connector=None, feeds=None, fetch_result=None
):
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

    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.get_connector_by_id",
        _fake_get_connector,
    )
    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.update_connector_last_indexed",
        _fake_update_last_indexed,
    )
    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.fetch_feed", _fake_fetch_feed
    )
    if feeds is not None:
        monkeypatch.setattr(
            "app.tasks.connector_indexers.rss_indexer.get_feeds_for_workspace",
            lambda config: feeds,
        )
    task_log = _FakeTaskLog()
    monkeypatch.setattr(
        "app.tasks.connector_indexers.rss_indexer.TaskLoggingService",
        lambda session, workspace_id: task_log,
    )
    return task_log


async def test_index_rss_feeds_connector_not_found(monkeypatch):
    log = _patch_index_rss_deps(monkeypatch, connector=None)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=99, workspace_id=7, user_id="u1"
    )
    assert (indexed, skipped) == (0, 0)
    assert "not found" in warning
    assert log.failures


async def test_index_rss_feeds_no_feeds_configured(monkeypatch):
    log = _patch_index_rss_deps(monkeypatch, connector=_FakeConnector(), feeds=[])
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert (indexed, skipped, warning) == (0, 0, None)
    assert log.successes == 1


async def test_index_rss_feeds_all_feeds_failed(monkeypatch):
    def _boom(url):
        raise RuntimeError("feed down")

    log = _patch_index_rss_deps(
        monkeypatch,
        connector=_FakeConnector(),
        feeds=["https://a/x"],
        fetch_result=_boom,
    )
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert (indexed, skipped) == (0, 0)
    assert "failed" in warning
    assert log.failures


async def test_index_rss_feeds_no_articles_returned(monkeypatch):
    log = _patch_index_rss_deps(
        monkeypatch, connector=_FakeConnector(), feeds=["https://a/x"], fetch_result=[]
    )
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

    async def _fake_upsert(session, **kwargs):
        return None

    async def _fake_prune(session, **kwargs):
        return 0

    monkeypatch.setattr(mod, "IndexingPipelineService", lambda session: _FakePipeline())
    monkeypatch.setattr(mod, "upsert_canonical_entity", _fake_upsert)
    monkeypatch.setattr(mod, "_prune_stale_articles", _fake_prune)
    indexed, skipped, warning = await index_rss_feeds(
        _PruneSession(rows=[]), connector_id=1, workspace_id=7, user_id="u1"
    )
    assert indexed == 1
    assert skipped == 0
    assert warning is None
    assert len(indexed_docs) == 1
