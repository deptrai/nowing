"""Unit tests for the kb_persistence embed-failure guard.

An embedding-provider failure must never lose a committed document: the row
still lands with ``embedding=None`` and ``content_needs_reindexing=True`` so
``reindex_document_task`` can rebuild the vectors afterwards.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.agents.chat.multi_agent_chat.main_agent.middleware.kb_persistence import (
    _commit as kb_commit,
    _helpers as kb_persistence,
)
from app.db import Document

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        return []

    def scalars(self) -> "_FakeResult":
        return self

    def first(self) -> Any:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.execute = AsyncMock(return_value=_FakeResult(None))
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self._next_id = 1

        async def _flush_assigning_ids() -> None:
            for obj in self.added:
                if getattr(obj, "id", None) is None:
                    obj.id = self._next_id
                    self._next_id += 1

        self.flush.side_effect = _flush_assigning_ids

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)


@pytest.fixture(autouse=True)
def _stub_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kb_persistence, "chunk_text", lambda content: [content])


@pytest.mark.asyncio
async def test_create_document_embed_failure_keeps_row_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embed raise on create -> doc persists, flagged, no chunks."""

    def _boom(texts: list[str]) -> list[Any]:
        raise RuntimeError("embedding provider down")

    monkeypatch.setattr(kb_persistence, "embed_texts", _boom)

    session = _FakeSession()
    doc = await kb_persistence._create_document(
        session,  # type: ignore[arg-type]
        virtual_path="/documents/a.md",
        content="# Hello",
        workspace_id=42,
        created_by_id="user-1",
    )

    assert isinstance(doc, Document)
    assert doc.embedding is None
    assert doc.content_needs_reindexing is True
    assert doc.document_metadata["index_status"] == "embed_failed"
    # No Chunk rows were staged for a failed embed.
    from app.db import Chunk

    assert not [row for row in session.added if isinstance(row, Chunk)]


@pytest.mark.asyncio
async def test_update_document_embed_failure_keeps_row_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embed raise on update -> edit persists, flagged for reindex."""

    def _boom(texts: list[str]) -> list[Any]:
        raise RuntimeError("embedding provider down")

    monkeypatch.setattr(kb_persistence, "embed_texts", _boom)

    existing = Document(
        id=7,
        workspace_id=42,
        title="a.md",
        content="old",
        document_metadata={"virtual_path": "/documents/a.md"},
    )
    session = _FakeSession()
    session.execute = AsyncMock(return_value=_FakeResult(value=existing))

    doc = await kb_persistence._update_document(
        session,  # type: ignore[arg-type]
        doc_id=7,
        content="# New",
        virtual_path="/documents/a.md",
        workspace_id=42,
    )

    assert doc is existing
    assert doc.content == "# New"
    assert doc.embedding is None
    assert doc.content_needs_reindexing is True
    assert doc.document_metadata["index_status"] == "embed_failed"


@pytest.mark.asyncio
async def test_update_document_chunk_failure_keeps_summary_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chunk-stage failure keeps the fresh summary embedding but flags reindex."""
    calls_made = [0]

    def _flaky(texts: list[str]) -> list[Any]:
        # First embed call is the summary; the chunk stage comes second.
        calls_made[0] += 1
        if calls_made[0] >= 2:
            raise RuntimeError("chunk embed down")
        return [np.zeros(8, dtype=np.float32)]

    monkeypatch.setattr(kb_persistence, "embed_texts", _flaky)

    existing = Document(
        id=8,
        workspace_id=42,
        title="a.md",
        content="old",
        document_metadata={"virtual_path": "/documents/a.md"},
    )
    session = _FakeSession()
    session.execute = AsyncMock(return_value=_FakeResult(value=existing))

    doc = await kb_persistence._update_document(
        session,  # type: ignore[arg-type]
        doc_id=8,
        content="# New",
        virtual_path="/documents/a.md",
        workspace_id=42,
    )

    assert doc is existing
    assert doc.embedding is not None  # summary embedding preserved
    assert doc.content_needs_reindexing is True
    assert doc.document_metadata["index_status"] == "embed_failed"


@pytest.mark.asyncio
async def test_update_document_success_heals_previously_flagged_doc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful edit on a flagged doc clears the flag and index_status."""
    monkeypatch.setattr(
        kb_persistence,
        "embed_texts",
        lambda texts: [np.zeros(8, dtype=np.float32) for _ in texts],
    )

    existing = Document(
        id=9,
        workspace_id=42,
        title="a.md",
        content="old",
        document_metadata={"virtual_path": "/documents/a.md", "index_status": "embed_failed"},
        content_needs_reindexing=True,
    )
    session = _FakeSession()
    session.execute = AsyncMock(return_value=_FakeResult(value=existing))

    doc = await kb_persistence._update_document(
        session,  # type: ignore[arg-type]
        doc_id=9,
        content="# New",
        virtual_path="/documents/a.md",
        workspace_id=42,
    )

    assert doc is existing
    assert doc.content_needs_reindexing is False
    assert "index_status" not in doc.document_metadata


@pytest.mark.asyncio
async def test_create_document_embed_success_clears_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Healthy embed path is unchanged: embedding set, flag untouched."""
    monkeypatch.setattr(
        kb_persistence,
        "embed_texts",
        lambda texts: [np.zeros(8, dtype=np.float32) for _ in texts],
    )

    session = _FakeSession()
    doc = await kb_persistence._create_document(
        session,  # type: ignore[arg-type]
        virtual_path="/documents/a.md",
        content="# Hello",
        workspace_id=42,
        created_by_id="user-1",
    )

    assert doc.embedding is not None
    assert not getattr(doc, "content_needs_reindexing", False)


# ---------------------------------------------------------------------------
# commit_staged_filesystem_state -> post-commit reindex dispatch
# ---------------------------------------------------------------------------


class _NestedCtx:
    async def __aenter__(self) -> "_NestedCtx":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _CommitSession(_FakeSession):
    def begin_nested(self) -> _NestedCtx:
        return _NestedCtx()


class _FakeSessionFactory:
    """Mimics ``shielded_async_session()`` (async context manager)."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def __aenter__(self) -> Any:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _make_shielded(monkeypatch: pytest.MonkeyPatch, session: Any) -> None:
    monkeypatch.setattr(
        kb_commit, "shielded_async_session", lambda: _FakeSessionFactory(session)
    )


@pytest.mark.asyncio
async def test_commit_schedules_reindex_for_embed_failed_doc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A doc committed with content_needs_reindexing triggers apply_async."""
    scheduled: list[tuple[int, str]] = []

    class _FakeTask:
        @staticmethod
        def apply_async(*, args: list[Any], countdown: int) -> None:
            scheduled.append((args[0], args[1]))

    monkeypatch.setattr(
        "app.tasks.celery_tasks.document_reindex_tasks.reindex_document_task",
        _FakeTask,
    )

    session = _CommitSession()
    session.execute = AsyncMock(return_value=_FakeResult(None))
    _make_shielded(monkeypatch, session)
    monkeypatch.setattr(
        kb_commit,
        "get_flags",
        lambda: MagicMock(enable_action_log=False),
    )

    flagged = Document(
        id=123,
        workspace_id=42,
        title="a.md",
        content="# Hello",
        document_metadata={"virtual_path": "/documents/a.md"},
        content_needs_reindexing=True,
    )

    async def _fake_create(*args: Any, **kwargs: Any) -> Document:
        return flagged

    monkeypatch.setattr(kb_commit, "_create_document", _fake_create)

    state = {
        "files": {"/documents/a.md": {"content": ["# Hello"]}},
        "dirty_paths": ["/documents/a.md"],
        "doc_id_by_path": {},
    }

    await kb_commit.commit_staged_filesystem_state(
        state,
        workspace_id=42,
        created_by_id="user-1",
        dispatch_events=False,
    )

    assert scheduled == [(123, "user-1")]


@pytest.mark.asyncio
async def test_commit_schedules_reindex_for_updated_flagged_doc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Update path: a flagged doc resolved via doc_id_by_path dispatches reindex."""
    scheduled: list[tuple[int, str]] = []

    class _FakeTask:
        @staticmethod
        def apply_async(*, args: list[Any], countdown: int) -> None:
            scheduled.append((args[0], args[1]))

    monkeypatch.setattr(
        "app.tasks.celery_tasks.document_reindex_tasks.reindex_document_task",
        _FakeTask,
    )

    session = _CommitSession()
    session.execute = AsyncMock(return_value=_FakeResult(None))
    _make_shielded(monkeypatch, session)
    monkeypatch.setattr(
        kb_commit,
        "get_flags",
        lambda: MagicMock(enable_action_log=False),
    )

    flagged = Document(
        id=321,
        workspace_id=42,
        title="a.md",
        content="# New",
        document_metadata={"virtual_path": "/documents/a.md"},
        content_needs_reindexing=True,
    )

    async def _fake_update(*args: Any, **kwargs: Any) -> Document:
        return flagged

    monkeypatch.setattr(kb_commit, "_update_document", _fake_update)

    state = {
        "files": {"/documents/a.md": {"content": ["# New"]}},
        "dirty_paths": ["/documents/a.md"],
        "doc_id_by_path": {"/documents/a.md": 321},
    }

    await kb_commit.commit_staged_filesystem_state(
        state,
        workspace_id=42,
        created_by_id="user-1",
        dispatch_events=False,
    )

    assert scheduled == [(321, "user-1")]


@pytest.mark.asyncio
async def test_commit_skips_reindex_when_embed_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No flag -> no reindex dispatch."""
    scheduled: list[Any] = []

    class _FakeTask:
        @staticmethod
        def apply_async(*, args: list[Any], countdown: int) -> None:
            scheduled.append(args)

    monkeypatch.setattr(
        "app.tasks.celery_tasks.document_reindex_tasks.reindex_document_task",
        _FakeTask,
    )

    session = _CommitSession()
    session.execute = AsyncMock(return_value=_FakeResult(None))
    _make_shielded(monkeypatch, session)
    monkeypatch.setattr(
        kb_commit,
        "get_flags",
        lambda: MagicMock(enable_action_log=False),
    )

    healthy = Document(
        id=124,
        workspace_id=42,
        title="a.md",
        content="# Hello",
        document_metadata={"virtual_path": "/documents/a.md"},
    )

    async def _fake_create(*args: Any, **kwargs: Any) -> Document:
        return healthy

    monkeypatch.setattr(kb_commit, "_create_document", _fake_create)

    state = {
        "files": {"/documents/a.md": {"content": ["# Hello"]}},
        "dirty_paths": ["/documents/a.md"],
        "doc_id_by_path": {},
    }

    await kb_commit.commit_staged_filesystem_state(
        state,
        workspace_id=42,
        created_by_id="user-1",
        dispatch_events=False,
    )

    assert scheduled == []
