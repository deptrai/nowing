"""Red-phase ATDD tests for Story 3.7: Data Retention & Lifecycle.

Verifies workspace retention settings persistence, validation/permissions,
document archive/soft-delete state, lifecycle task multi-tenancy, and
visibility filtering across lists, search, title search, type counts, and
single-document reads.

All tests are intentionally skipped while the feature is being implemented
(TDD red phase).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.config import config as app_config
from app.db import Chunk, Document, DocumentStatus, DocumentType, Workspace
from app.routes.workspaces_routes import create_default_roles_and_membership

pytestmark = pytest.mark.integration

BASE = "/api/v1/workspaces"
DOCUMENTS_BASE = "/api/v1/documents"
EMBEDDING_DIM = app_config.embedding_model_instance.dimension
DUMMY_EMBEDDING = [0.1] * EMBEDDING_DIM


class _NoopSessionContext:
    """Async context manager that simply yields the supplied session."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return None


def _make_document(
    *,
    title: str,
    content: str,
    workspace_id: int,
    created_by_id: str,
    created_at: datetime | None = None,
    archived_at: datetime | None = None,
) -> Document:
    """Create a Document instance for red-phase tests.

    TODO: ``archived_at`` will exist after migration 176 is applied.
    """
    return Document(
        title=title,
        document_type=DocumentType.NOTE,
        content=content,
        content_hash=uuid.uuid4().hex,
        unique_identifier_hash=uuid.uuid4().hex,
        source_markdown=content,
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        created_at=created_at or datetime.now(UTC),
        updated_at=datetime.now(UTC),
        document_metadata={},
        status=DocumentStatus.ready(),
        archived_at=archived_at,
    )


def _make_chunk(*, content: str, document_id: int, position: int = 0) -> Chunk:
    return Chunk(
        content=content,
        document_id=document_id,
        position=position,
        embedding=DUMMY_EMBEDDING,
    )


# ---------------------------------------------------------------------------
# AC 2: Settings persist per workspace
# ---------------------------------------------------------------------------


async def test_owner_can_update_and_retrieve_retention_settings(client, db_workspace):
    """PUT and GET /workspaces/{id} must round-trip retention settings."""
    payload = {
        "document_retention_days": 30,
        "auto_archive_enabled": True,
        "document_retention_action": "archive",
    }
    put_resp = await client.put(f"{BASE}/{db_workspace.id}", json=payload)
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["document_retention_days"] == 30
    assert body["auto_archive_enabled"] is True
    assert body["document_retention_action"] == "archive"

    get_resp = await client.get(f"{BASE}/{db_workspace.id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["document_retention_days"] == 30
    assert data["auto_archive_enabled"] is True
    assert data["document_retention_action"] == "archive"


# ---------------------------------------------------------------------------
# AC 7: Validation & permissions
# ---------------------------------------------------------------------------


async def test_update_retention_rejects_zero_days_when_auto_archive_enabled(client, db_workspace):
    """Enabling auto-archive requires a positive document_retention_days value."""
    resp = await client.put(
        f"{BASE}/{db_workspace.id}",
        json={"auto_archive_enabled": True, "document_retention_days": 0},
    )
    assert resp.status_code == 400


async def test_update_retention_rejects_invalid_action(client, db_workspace):
    """Only 'archive' or 'delete' are valid retention actions."""
    resp = await client.put(
        f"{BASE}/{db_workspace.id}",
        json={"document_retention_action": "purge"},
    )
    assert resp.status_code == 422


async def test_non_owner_cannot_update_retention_settings(client_as_editor, db_workspace):
    """Editors/Viewers must receive 403 when mutating workspace retention settings."""
    resp = await client_as_editor.put(
        f"{BASE}/{db_workspace.id}",
        json={"document_retention_days": 7, "auto_archive_enabled": True},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AC 3 & AC 5: Document archive/soft-delete state and visibility filtering
# ---------------------------------------------------------------------------


async def test_archived_document_excluded_from_document_list(client, db_workspace, db_user, db_session):
    """Archived documents must not appear in /documents list or counts."""
    user_id = str(db_user.id)
    visible = _make_document(
        title="Visible doc",
        content="visible",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
    )
    archived = _make_document(
        title="Archived doc",
        content="archived",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
        archived_at=datetime.now(UTC),
    )
    db_session.add_all([visible, archived])
    await db_session.flush()

    resp = await client.get(f"{DOCUMENTS_BASE}?workspace_id={db_workspace.id}")
    assert resp.status_code == 200
    data = resp.json()
    titles = {d["title"] for d in data["items"]}
    assert "Visible doc" in titles
    assert "Archived doc" not in titles
    assert data["total"] == 1


async def test_archived_document_excluded_from_search(client, db_workspace, db_user, db_session):
    """Archived documents must not appear in /documents/search results."""
    user_id = str(db_user.id)
    doc = _make_document(
        title="Secret report",
        content="content",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
        archived_at=datetime.now(UTC),
    )
    db_session.add(doc)
    await db_session.flush()

    resp = await client.get(
        f"{DOCUMENTS_BASE}/search?workspace_id={db_workspace.id}&title=Secret"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(d["title"] != "Secret report" for d in data["items"])
    assert data["total"] == 0


async def test_archived_document_excluded_from_title_search(
    client, db_workspace, db_user, db_session
):
    """Archived documents must not appear in /documents/search/titles results."""
    user_id = str(db_user.id)
    doc = _make_document(
        title="Old spec",
        content="content",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
        archived_at=datetime.now(UTC),
    )
    db_session.add(doc)
    await db_session.flush()

    resp = await client.get(
        f"{DOCUMENTS_BASE}/search/titles?workspace_id={db_workspace.id}&title=Old"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(d["title"] != "Old spec" for d in data["items"])


async def test_archived_document_excluded_from_type_counts(
    client, db_workspace, db_user, db_session
):
    """Type-counts endpoint must exclude archived documents."""
    user_id = str(db_user.id)
    visible = _make_document(
        title="Visible",
        content="v",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
    )
    archived = _make_document(
        title="Archived",
        content="a",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
        archived_at=datetime.now(UTC),
    )
    db_session.add_all([visible, archived])
    await db_session.flush()

    resp = await client.get(f"{DOCUMENTS_BASE}/type-counts?workspace_id={db_workspace.id}")
    assert resp.status_code == 200
    counts = resp.json()
    assert counts.get("NOTE", 0) == 1


async def test_archived_document_read_by_id_returns_404(
    client, db_workspace, db_user, db_session
):
    """GET /documents/{id} must return 404 for archived documents."""
    user_id = str(db_user.id)
    doc = _make_document(
        title="Archived",
        content="a",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
        archived_at=datetime.now(UTC),
    )
    db_session.add(doc)
    await db_session.flush()

    resp = await client.get(f"{DOCUMENTS_BASE}/{doc.id}")
    assert resp.status_code == 404


async def test_document_read_exposes_archived_at_for_non_archived_documents(
    client, db_workspace, db_user, db_session
):
    """GET /documents/{id} must include archived_at (null for active documents)."""
    user_id = str(db_user.id)
    doc = _make_document(
        title="Active",
        content="a",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
    )
    db_session.add(doc)
    await db_session.flush()

    resp = await client.get(f"{DOCUMENTS_BASE}/{doc.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "archived_at" in data
    assert data["archived_at"] is None


async def test_archived_document_get_by_chunk_id_returns_404(
    client, db_workspace, db_user, db_session
):
    """GET /documents/by-chunk/{chunk_id} must return 404 for archived documents."""
    user_id = str(db_user.id)
    doc = _make_document(
        title="Archived",
        content="content",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
        archived_at=datetime.now(UTC),
    )
    db_session.add(doc)
    await db_session.flush()

    chunk = _make_chunk(content="chunk", document_id=doc.id)
    db_session.add(chunk)
    await db_session.flush()

    resp = await client.get(f"{DOCUMENTS_BASE}/by-chunk/{chunk.id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC 6: Real-time sync (backend publication)
# ---------------------------------------------------------------------------


def test_zero_publication_includes_archived_at_for_real_time_sync():
    """Archived documents must be published to Zero so the web client can filter them."""
    from app.zero_publication import DOCUMENT_COLS

    assert "archived_at" in DOCUMENT_COLS


# ---------------------------------------------------------------------------
# AC 3 & AC 4: Celery lifecycle task
# ---------------------------------------------------------------------------


async def test_retention_task_archives_old_documents(
    db_workspace, db_user, db_session, monkeypatch
):
    """The daily task archives documents older than workspace.document_retention_days."""
    document_retention_task = pytest.importorskip(
        "app.tasks.celery_tasks.document_retention_task"
    )

    # Configure workspace with a 2-day retention policy.
    db_workspace.auto_archive_enabled = True
    db_workspace.document_retention_days = 2
    db_workspace.document_retention_action = "archive"
    await db_session.flush()

    old_doc = _make_document(
        title="Old doc",
        content="old",
        workspace_id=db_workspace.id,
        created_by_id=str(db_user.id),
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    db_session.add(old_doc)
    await db_session.flush()

    # Run the task inside the test transaction so the result is visible.
    monkeypatch.setattr(
        document_retention_task,
        "get_celery_session_maker",
        lambda: lambda: _NoopSessionContext(db_session),
    )
    monkeypatch.setattr(
        document_retention_task,
        "delete_document_task",
        type("FakeTask", (), {"delay": lambda *args, **kwargs: None})(),
    )

    await document_retention_task._apply_retention()
    await db_session.refresh(old_doc)

    assert old_doc.archived_at is not None


async def test_retention_task_only_touches_matching_workspace(
    db_workspace, db_user, db_session, monkeypatch
):
    """The lifecycle task must only archive documents in workspaces with auto_archive enabled."""
    document_retention_task = pytest.importorskip(
        "app.tasks.celery_tasks.document_retention_task"
    )

    # Workspace 1 has retention enabled.
    db_workspace.auto_archive_enabled = True
    db_workspace.document_retention_days = 1
    db_workspace.document_retention_action = "archive"

    # Workspace 2 does not.
    other_workspace = Workspace(name="Other space", user_id=db_user.id)
    db_session.add(other_workspace)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, other_workspace.id, db_user.id)

    user_id = str(db_user.id)
    old_doc_1 = _make_document(
        title="Old in enabled workspace",
        content="x",
        workspace_id=db_workspace.id,
        created_by_id=user_id,
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    old_doc_2 = _make_document(
        title="Old in disabled workspace",
        content="y",
        workspace_id=other_workspace.id,
        created_by_id=user_id,
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    db_session.add_all([old_doc_1, old_doc_2])
    await db_session.flush()

    monkeypatch.setattr(
        document_retention_task,
        "get_celery_session_maker",
        lambda: lambda: _NoopSessionContext(db_session),
    )
    monkeypatch.setattr(
        document_retention_task,
        "delete_document_task",
        type("FakeTask", (), {"delay": lambda *args, **kwargs: None})(),
    )

    await document_retention_task._apply_retention()
    await db_session.refresh(old_doc_1)
    await db_session.refresh(old_doc_2)

    assert old_doc_1.archived_at is not None
    assert old_doc_2.archived_at is None


async def test_delete_strategy_dispatches_delete_document_task(
    db_workspace, db_user, db_session, monkeypatch
):
    """When the retention action is 'delete', the task must dispatch delete_document_task."""
    from unittest.mock import MagicMock

    document_retention_task = pytest.importorskip(
        "app.tasks.celery_tasks.document_retention_task"
    )

    db_workspace.auto_archive_enabled = True
    db_workspace.document_retention_days = 1
    db_workspace.document_retention_action = "delete"
    await db_session.flush()

    old_doc = _make_document(
        title="To delete",
        content="x",
        workspace_id=db_workspace.id,
        created_by_id=str(db_user.id),
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    db_session.add(old_doc)
    await db_session.flush()

    delete_mock = MagicMock()
    monkeypatch.setattr(
        document_retention_task,
        "get_celery_session_maker",
        lambda: lambda: _NoopSessionContext(db_session),
    )
    monkeypatch.setattr(document_retention_task, "delete_document_task", delete_mock)

    await document_retention_task._apply_retention()
    await db_session.refresh(old_doc)

    delete_mock.delay.assert_called_once_with(old_doc.id)
    assert old_doc.status == {"state": "deleting"}
