"""Unit tests for canonical cleanup helpers used by connector lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.canonical.services.canonical_cleanup import (
    delete_canonical_sources_by_record_ids,
    delete_orphaned_canonical_entities,
)

pytestmark = [pytest.mark.unit]


@dataclass
class FakeResult:
    rowcount: int


@dataclass
class FakeSession:
    """Minimal AsyncSession recording every executed statement."""

    statements: list = field(default_factory=list)
    rowcounts: list[int] = field(default_factory=list)

    async def execute(self, statement) -> FakeResult:
        self.statements.append(statement)
        rowcount = 0
        if self.rowcounts:
            rowcount = self.rowcounts.pop(0)
        return FakeResult(rowcount=rowcount)

    async def commit(self) -> None:  # pragma: no cover - unused
        pass


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


async def test_delete_sources_batches_and_sums_rowcounts():
    session = FakeSession(rowcounts=[2, 3])
    total = await delete_canonical_sources_by_record_ids(
        session, workspace_id=7, record_ids=[f"link-{i}" for i in range(600)]
    )
    assert total == 5
    assert len(session.statements) == 2
    for stmt, ids in zip(
        session.statements,
        ([f"link-{i}" for i in range(500)], [f"link-{i}" for i in range(500, 600)]),
        strict=True,
    ):
        sql = _sql(stmt)
        assert sql.startswith("DELETE FROM canonical_entity_sources")
        assert "canonical_entity_sources.workspace_id = 7" in sql
        assert all(f"'{link}'" in sql for link in ids)


async def test_delete_sources_empty_input_is_noop():
    session = FakeSession()
    total = await delete_canonical_sources_by_record_ids(
        session, workspace_id=7, record_ids=[]
    )
    assert total == 0
    assert session.statements == []


async def test_delete_sources_single_batch_under_limit():
    session = FakeSession(rowcounts=[1])
    total = await delete_canonical_sources_by_record_ids(
        session, workspace_id=7, record_ids=["only"]
    )
    assert total == 1
    assert len(session.statements) == 1
    assert "'only'" in _sql(session.statements[0])


async def test_delete_orphaned_entities_scoped_to_types():
    session = FakeSession(rowcounts=[4])
    total = await delete_orphaned_canonical_entities(
        session, workspace_id=7, entity_types=["news_article"]
    )
    assert total == 4
    sql = _sql(session.statements[0])
    assert sql.startswith("DELETE FROM canonical_entities")
    assert "canonical_entities.workspace_id = 7" in sql
    assert "canonical_entities.entity_type IN ('news_article')" in sql
    assert "EXISTS" in sql
    assert "NOT" in sql
    assert "canonical_entity_sources.canonical_entity_id = canonical_entities.id" in sql


async def test_delete_orphaned_entities_without_type_scope():
    session = FakeSession(rowcounts=[9])
    total = await delete_orphaned_canonical_entities(session, workspace_id=7)
    assert total == 9
    sql = _sql(session.statements[0])
    assert "entity_type IN" not in sql
    assert "EXISTS" in sql
    assert "NOT" in sql


async def test_delete_orphaned_entities_returns_zero_when_no_rows():
    session = FakeSession(rowcounts=[0])
    total = await delete_orphaned_canonical_entities(
        session, workspace_id=7, entity_types=["news_article"]
    )
    assert total == 0
    assert len(session.statements) == 1


async def test_helpers_target_correct_tables():
    """The helpers must never delete outside their two tables."""
    session = FakeSession()
    await delete_canonical_sources_by_record_ids(
        session, workspace_id=1, record_ids=["a"]
    )
    await delete_orphaned_canonical_entities(session, workspace_id=1)
    sqls = [_sql(stmt) for stmt in session.statements]
    assert any(sql.startswith("DELETE FROM canonical_entity_sources") for sql in sqls)
    assert any(sql.startswith("DELETE FROM canonical_entities") for sql in sqls)
    assert all("documents" not in sql for sql in sqls)
    assert all("chunks" not in sql for sql in sqls)


class _UpsertSession:
    """Minimal async session double for upsert_canonical_entity unit tests."""

    def __init__(self, existing=None, *, source_ids=None):
        self.existing = existing
        self.source_ids = source_ids or []
        self.info = {}
        self.added = []
        self.flushes = 0
        self.commits = 0
        self.get_calls = []
        self.executes = []

    async def execute(self, stmt, params=None):
        self.executes.append((stmt, params))
        return None

    async def scalar(self, stmt):
        return self.existing

    async def get(self, model, ident):
        self.get_calls.append(ident)
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


class _ExistingEntity:
    def __init__(self, **kwargs):
        defaults = {
            "id": "11111111-1111-1111-1111-111111111111",
            "version": 2,
            "canonical_title": "Flood warnings issued in northern Vietnam",
            "canonical_data": {
                "title": "Flood warnings issued in northern Vietnam",
                "link": "https://vnexpress.net/article/flood-warnings",
                "category": "Weather",
            },
            "search_text": "old search text",
            "conflict_flags": [],
            "confidence_score": 0.9,
            "last_seen_at": None,
            "source_count": 1,
            "embedding_status": "ready",
            "embedding": b"old",
            "embedding_model_name": "old-model",
            "embedding_content_hash": "old-hash",
            "workspace_id": 7,
            "entity_type": "news_article",
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def _patch_persist_helpers(monkeypatch, *, sources=None, source_count=1, prev_id=None):
    import app.canonical.services.canonical_persist_service as mod

    calls = {"merge": [], "enqueue": 0, "upsert_source": []}

    async def _fake_upsert_source(session, entity, **kwargs):
        calls["upsert_source"].append((entity, kwargs))
        return prev_id

    async def _fake_source_ids(session, entity_id):
        return sources or []

    async def _fake_update_source_count(session, entity_id):
        return source_count

    async def _fake_merge_history(session, **kwargs):
        calls["merge"].append(kwargs)

    async def _fake_enqueue(entity):
        calls["enqueue"] += 1

    monkeypatch.setattr(mod, "_upsert_source", _fake_upsert_source)
    monkeypatch.setattr(mod, "_source_ids_for_entity", _fake_source_ids)
    monkeypatch.setattr(mod, "_update_source_count", _fake_update_source_count)
    monkeypatch.setattr(mod, "record_merge_history", _fake_merge_history)
    monkeypatch.setattr(mod, "_enqueue_embedding_backfill", _fake_enqueue)
    return calls


def _sample_kwargs(**overrides):
    kwargs = {
        "workspace_id": 7,
        "entity_type": "news_article",
        "fingerprint": "abc123",
        "title": "Flood warnings issued in northern Vietnam",
        "data": {"title": "Flood warnings issued in northern Vietnam", "link": "x"},
        "search_text": "Flood warnings issued in northern Vietnam x",
        "source_name": "rss:vnexpress.net",
        "source_record_id": "https://vnexpress.net/article/flood-warnings",
        "actor": "rss-connector:9",
        "merge_method": "rss_fingerprint",
        "confidence_score": 0.9,
    }
    kwargs.update(overrides)
    return kwargs


async def test_upsert_new_entity_records_create_and_backfill(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    calls = _patch_persist_helpers(
        monkeypatch, sources=[{"source_name": "a", "source_record_id": "b"}]
    )
    session = _UpsertSession(existing=None)
    entity = await mod.upsert_canonical_entity(session, **_sample_kwargs())
    assert entity.version == 1
    assert entity.source_count == 1
    assert entity.embedding_status == "pending"
    assert session.flushes == 1
    assert calls["merge"][0]["operation"] == "create"
    assert calls["merge"][0]["new_version"] == 1
    assert calls["enqueue"] == 1
    assert session.info["canonical_workspace_id"] == 7


async def test_upsert_existing_unchanged_content_only_touches_timestamp(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    calls = _patch_persist_helpers(monkeypatch)
    existing = _ExistingEntity(
        search_text="Flood warnings issued in northern Vietnam x",
        canonical_data=_sample_kwargs()["data"],
        confidence_score=0.9,
    )
    session = _UpsertSession(existing=existing)
    entity = await mod.upsert_canonical_entity(
        session, **_sample_kwargs(search_text=existing.search_text)
    )
    assert entity is existing
    assert entity.version == 2  # unchanged
    assert calls["merge"] == []  # no churn on re-poll
    assert calls["enqueue"] == 0
    assert entity.last_seen_at is not None


async def test_upsert_existing_changed_content_bumps_version_and_resets_embedding(
    monkeypatch,
):
    import app.canonical.services.canonical_persist_service as mod

    calls = _patch_persist_helpers(monkeypatch)
    session = _UpsertSession(existing=_ExistingEntity())
    entity = await mod.upsert_canonical_entity(
        session, **_sample_kwargs(search_text="brand new text")
    )
    assert entity.version == 3
    assert entity.embedding_status == "pending"
    assert entity.embedding is None
    assert calls["merge"][0]["operation"] == "merge"
    assert calls["merge"][0]["new_version"] == 3
    assert calls["enqueue"] == 1


async def test_upsert_expected_version_mismatch_raises(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    _patch_persist_helpers(monkeypatch)
    session = _UpsertSession(existing=_ExistingEntity(version=5))
    with pytest.raises(mod.ConcurrentUpdateError):
        await mod.upsert_canonical_entity(session, **_sample_kwargs(expected_version=4))


async def test_upsert_expected_version_nonzero_for_new_entity_raises(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    _patch_persist_helpers(monkeypatch)
    session = _UpsertSession(existing=None)
    with pytest.raises(mod.ConcurrentUpdateError):
        await mod.upsert_canonical_entity(session, **_sample_kwargs(expected_version=2))


async def test_upsert_source_moved_updates_previous_entity(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    prev_id = "99999999-9999-9999-9999-999999999999"
    calls = _patch_persist_helpers(
        monkeypatch,
        sources=[{"source_name": "a", "source_record_id": "b"}],
        prev_id=prev_id,
    )
    session = _UpsertSession(existing=_ExistingEntity(search_text="new text"))
    entity = await mod.upsert_canonical_entity(
        session, **_sample_kwargs(search_text="new text")
    )
    assert prev_id in session.get_calls
    assert entity.version == 3
    assert calls["merge"] != []


class _HistoryEntry:
    def __init__(self, **kwargs):
        defaults = {
            "id": "22222222-2222-2222-2222-222222222222",
            "canonical_entity_id": "11111111-1111-1111-1111-111111111111",
            "new_version": 2,
            "previous_data": {"title": "old", "link": "old-link", "id": "drop-me"},
            "conflicts": [{"field": "title"}],
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class _RevertSession(_UpsertSession):
    """Session double whose scalar() returns queued values in order."""

    def __init__(self, scalars, *, rowcount=1):
        super().__init__(existing=None)
        self._scalars = list(scalars)
        self.rowcount = rowcount
        self.refreshed = []

    async def scalar(self, stmt):
        if self._scalars:
            return self._scalars.pop(0)
        return None

    async def execute(self, stmt, params=None):
        self.executes.append((stmt, params))
        return _RowCountResult(self.rowcount)

    async def refresh(self, obj):
        self.refreshed.append(obj)


class _RowCountResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


def test_revert_data_drops_identity_columns():
    from app.canonical.services.canonical_persist_service import _revert_data

    reverted = _revert_data(
        {
            "id": "x",
            "workspace_id": 1,
            "entity_type": "t",
            "fingerprint": "f",
            "title": "kept",
            "link": "kept-link",
        }
    )
    assert reverted == {"title": "kept", "link": "kept-link"}


def test_conflict_matches_field_exact_field_and_type():
    from app.canonical.services.canonical_persist_service import _conflict_matches_field

    assert _conflict_matches_field({"field": "canonical_title"}, "canonical_title")
    assert _conflict_matches_field(
        {"type": "canonical_title_conflict"}, "canonical_title"
    )
    assert _conflict_matches_field({"type": "title_conflict"}, "title")
    assert not _conflict_matches_field({"type": "price"}, "title")


async def test_find_previous_canonical_entity_id_returns_scalar(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    session = _RevertSession(scalars=["uuid-1"])
    found = await mod._find_previous_canonical_entity_id(
        session, 7, "news_article", "rss:vnexpress.net", "https://x/a"
    )
    assert found == "uuid-1"
    assert session._scalars == []


async def test_update_source_count_defaults_zero(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    session = _RevertSession(scalars=[None])
    assert await mod._update_source_count(session, "uuid-1") == 0

    session = _RevertSession(scalars=[5])
    assert await mod._update_source_count(session, "uuid-1") == 5


async def test_source_ids_for_entity_maps_rows(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    class _Rows:
        def __init__(self):
            self.rows = [("rss:a", "https://a/1"), ("rss:b", "https://b/2")]

        def __iter__(self):
            return iter(self.rows)

    session = _RevertSession(scalars=[])
    session._rows = _Rows()

    async def _fake_execute(stmt, params=None):
        return session._rows

    import types

    session.execute = types.MethodType(_fake_execute, session)
    ids = await mod._source_ids_for_entity(session, "uuid-1")
    assert ids == [
        {"source_name": "rss:a", "source_record_id": "https://a/1"},
        {"source_name": "rss:b", "source_record_id": "https://b/2"},
    ]


async def test_revert_success_path(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    calls = _patch_persist_helpers(
        monkeypatch, sources=[{"source_name": "a", "source_record_id": "b"}]
    )
    current = _ExistingEntity(canonical_data={"title": "current", "link": "c"})
    history = _HistoryEntry()
    session = _RevertSession(scalars=[current, history])
    entity = await mod.revert_canonical_entity(
        session, 7, current.id, history.id, actor="admin"
    )
    assert entity is current
    assert session.executes  # UPDATE ran with the rowcount guard
    assert "canonical_data" in str(session.executes[1][0])
    assert calls["merge"][0]["operation"] == "revert"
    assert calls["merge"][0]["method"] == "revert_to_history"
    assert calls["enqueue"] == 1


async def test_revert_entity_not_found_raises(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    _patch_persist_helpers(monkeypatch)
    session = _RevertSession(scalars=[None])
    with pytest.raises(mod.RevertNotPossibleError):
        await mod.revert_canonical_entity(session, 7, "uuid-x", "uuid-h")


async def test_revert_history_not_found_raises(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    _patch_persist_helpers(monkeypatch)
    session = _RevertSession(scalars=[_ExistingEntity(), None])
    with pytest.raises(mod.RevertNotPossibleError):
        await mod.revert_canonical_entity(session, 7, "uuid-x", "uuid-h")


async def test_revert_version_mismatch_raises(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    _patch_persist_helpers(monkeypatch)
    session = _RevertSession(scalars=[_ExistingEntity(version=5), _HistoryEntry()])
    with pytest.raises(mod.RevertNotPossibleError):
        await mod.revert_canonical_entity(session, 7, "uuid-x", "uuid-h")


async def test_revert_rowcount_mismatch_raises(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    _patch_persist_helpers(monkeypatch)
    session = _RevertSession(scalars=[_ExistingEntity(), _HistoryEntry()], rowcount=0)
    with pytest.raises(mod.ConcurrentUpdateError):
        await mod.revert_canonical_entity(session, 7, "uuid-x", "uuid-h")


async def test_resolve_conflict_clears_matching_flags_and_sets_title(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    calls = _patch_persist_helpers(monkeypatch)
    entity = _ExistingEntity(
        conflict_flags=[
            {"field": "canonical_title"},
            {"type": "price"},
        ]
    )
    session = _RevertSession(scalars=[entity])
    resolved = await mod.resolve_canonical_conflict(
        session, 7, entity.id, "canonical_title", "New Title", actor="admin"
    )
    assert resolved is entity
    assert entity.canonical_title == "New Title"
    assert entity.canonical_data["canonical_title"] == "New Title"
    assert entity.conflict_flags == [{"type": "price"}]
    assert entity.version == 3
    assert entity.embedding_status == "pending"
    assert calls["merge"][0]["operation"] == "resolve"
    assert calls["merge"][0]["conflicts"] == [{"field": "canonical_title"}]
    assert calls["enqueue"] == 1


async def test_resolve_conflict_entity_not_found_raises(monkeypatch):
    import app.canonical.services.canonical_persist_service as mod

    _patch_persist_helpers(monkeypatch)
    session = _RevertSession(scalars=[None])
    with pytest.raises(mod.RevertNotPossibleError):
        await mod.resolve_canonical_conflict(session, 7, "uuid-x", "title", "v")
