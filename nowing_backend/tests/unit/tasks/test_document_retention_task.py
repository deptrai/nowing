"""Red-phase unit tests for the document retention lifecycle Celery task.

These tests are intentionally skipped until
``app/tasks/celery_tasks/document_retention_task.py`` is implemented
(Story 3.7, AC 3 & AC 4).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


class _FakeScalars:
    """Minimal stand-in for SQLAlchemy ScalarResult."""

    def __init__(self, items):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)


class _FakeResult:
    """Minimal stand-in for SQLAlchemy Result."""

    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return _FakeScalars(self._items)


class _NoopSessionContext:
    """Async context manager that yields the supplied session without tx management."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return None


class _FakeSession:
    """In-memory session that returns the configured workspaces then documents."""

    def __init__(self, workspaces, documents):
        self._workspaces = list(workspaces)
        self._documents = list(documents)
        self.commit_count = 0
        self._calls = 0

    async def execute(self, _stmt):
        self._calls += 1
        # First execute is the Workspace sweep; subsequent executes are Document queries.
        if self._calls == 1:
            return _FakeResult(self._workspaces)
        return _FakeResult(self._documents)

    async def commit(self):
        self.commit_count += 1


def _make_workspace(*, action: str = "archive"):
    return SimpleNamespace(
        id=1,
        auto_archive_enabled=True,
        document_retention_days=2,
        document_retention_action=action,
    )


def _make_old_document(*, status_state: str = "ready"):
    return SimpleNamespace(
        id=101,
        workspace_id=1,
        created_at=datetime.now(UTC) - timedelta(days=5),
        archived_at=None,
        status={"state": status_state},
    )


def test_retention_task_archives_old_documents(monkeypatch):
    """An old ready document in an auto-archive workspace gets archived_at set."""
    document_retention_task = pytest.importorskip(
        "app.tasks.celery_tasks.document_retention_task"
    )

    workspace = _make_workspace(action="archive")
    document = _make_old_document()
    fake_session = _FakeSession([workspace], [document])
    delete_mock = MagicMock()

    monkeypatch.setattr(
        document_retention_task,
        "get_celery_session_maker",
        lambda: lambda: _NoopSessionContext(fake_session),
    )
    monkeypatch.setattr(document_retention_task, "delete_document_task", delete_mock)

    document_retention_task.apply_document_retention_policies()

    assert document.archived_at is not None
    assert document.status == {"state": "ready"}
    assert delete_mock.delay.called is False
    assert fake_session.commit_count >= 1


def test_delete_strategy_dispatches_delete_document_task(monkeypatch):
    """When action is 'delete', the task archives then dispatches delete_document_task."""
    document_retention_task = pytest.importorskip(
        "app.tasks.celery_tasks.document_retention_task"
    )

    workspace = _make_workspace(action="delete")
    document = _make_old_document()
    fake_session = _FakeSession([workspace], [document])
    delete_mock = MagicMock()

    monkeypatch.setattr(
        document_retention_task,
        "get_celery_session_maker",
        lambda: lambda: _NoopSessionContext(fake_session),
    )
    monkeypatch.setattr(document_retention_task, "delete_document_task", delete_mock)

    document_retention_task.apply_document_retention_policies()

    assert document.archived_at is not None
    assert document.status == {"state": "deleting"}
    delete_mock.delay.assert_called_once_with(document.id)


def test_retention_task_skips_workspace_without_auto_archive(monkeypatch):
    """Workspaces with auto_archive_enabled=False are ignored entirely."""
    document_retention_task = pytest.importorskip(
        "app.tasks.celery_tasks.document_retention_task"
    )

    workspace = SimpleNamespace(
        id=1,
        auto_archive_enabled=False,
        document_retention_days=2,
        document_retention_action="archive",
    )
    document = _make_old_document()
    fake_session = _FakeSession([workspace], [document])
    delete_mock = MagicMock()

    monkeypatch.setattr(
        document_retention_task,
        "get_celery_session_maker",
        lambda: lambda: _NoopSessionContext(fake_session),
    )
    monkeypatch.setattr(document_retention_task, "delete_document_task", delete_mock)

    document_retention_task.apply_document_retention_policies()

    assert document.archived_at is None
    assert delete_mock.delay.called is False
