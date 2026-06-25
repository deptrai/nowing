"""Unit tests for Dropbox delta-sync and orchestrator — E1-E4, F1-F3."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from tests.unit.connector_indexers.conftest import CONNECTOR_USER_ID, CONNECTOR_ID, CONNECTOR_SEARCH_SPACE_ID

from app.tasks.connector_indexers.dropbox_indexer import (
    _index_with_delta_sync,
    index_dropbox_files,
)

pytestmark = pytest.mark.unit



def _make_file_dict(file_id: str, name: str) -> dict:
    return {
        "id": file_id,
        "name": name,
        ".tag": "file",
        "path_lower": f"/{name}",
        "server_modified": "2026-01-01T00:00:00Z",
        "content_hash": f"hash_{file_id}",
    }


# ---------------------------------------------------------------------------
# E1-E4: _index_with_delta_sync tests
# ---------------------------------------------------------------------------


async def test_delta_sync_deletions_call_remove_document(monkeypatch):
    """E1: deleted entries are processed via _remove_document."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    entries = [
        {
            ".tag": "deleted",
            "name": "gone.txt",
            "path_lower": "/gone.txt",
            "id": "id:del1",
        },
        {
            ".tag": "deleted",
            "name": "also_gone.pdf",
            "path_lower": "/also_gone.pdf",
            "id": "id:del2",
        },
    ]

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=(entries, "new-cursor", None))

    remove_calls: list[str] = []

    async def _fake_remove(session, file_id, search_space_id):
        remove_calls.append(file_id)

    monkeypatch.setattr(_mod, "_remove_document", _fake_remove)
    monkeypatch.setattr(_mod, "_download_and_index", AsyncMock(return_value=(0, 0)))

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    _indexed, _skipped, _unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        "old-cursor",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert sorted(remove_calls) == ["id:del1", "id:del2"]
    assert cursor == "new-cursor"


async def test_delta_sync_upserts_filtered_and_downloaded(monkeypatch):
    """E2: modified/new file entries go through skip filter then download+index."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    entries = [
        _make_file_dict("mod1", "modified1.txt"),
        _make_file_dict("mod2", "modified2.txt"),
    ]

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=(entries, "cursor-v2", None))

    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_mock = AsyncMock(return_value=(2, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_mock)

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped, _unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        "cursor-v1",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert indexed == 2
    assert skipped == 0
    assert cursor == "cursor-v2"

    downloaded_files = download_mock.call_args[0][2]
    assert len(downloaded_files) == 2
    assert {f["id"] for f in downloaded_files} == {"mod1", "mod2"}


async def test_delta_sync_mix_deletions_and_upserts(monkeypatch):
    """E3: deletions processed, then remaining upserts filtered and indexed."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    entries = [
        {
            ".tag": "deleted",
            "name": "removed.txt",
            "path_lower": "/removed.txt",
            "id": "id:del1",
        },
        {
            ".tag": "deleted",
            "name": "trashed.pdf",
            "path_lower": "/trashed.pdf",
            "id": "id:del2",
        },
        _make_file_dict("mod1", "updated.txt"),
        _make_file_dict("new1", "brandnew.docx"),
    ]

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=(entries, "final-cursor", None))

    remove_calls: list[str] = []

    async def _fake_remove(session, file_id, search_space_id):
        remove_calls.append(file_id)

    monkeypatch.setattr(_mod, "_remove_document", _fake_remove)
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_mock = AsyncMock(return_value=(2, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_mock)

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped, _unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        "old-cursor",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert sorted(remove_calls) == ["id:del1", "id:del2"]
    assert indexed == 2
    assert skipped == 0
    assert cursor == "final-cursor"

    downloaded_files = download_mock.call_args[0][2]
    assert {f["id"] for f in downloaded_files} == {"mod1", "new1"}


async def test_delta_sync_returns_new_cursor(monkeypatch):
    """E4: the new cursor from the API response is returned."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_client = MagicMock()
    mock_client.get_changes = AsyncMock(return_value=([], "brand-new-cursor-xyz", None))

    monkeypatch.setattr(_mod, "_download_and_index", AsyncMock(return_value=(0, 0)))

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    indexed, skipped, _unsupported, cursor = await _index_with_delta_sync(
        mock_client,
        AsyncMock(),
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        "old-cursor",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    assert cursor == "brand-new-cursor-xyz"
    assert indexed == 0
    assert skipped == 0


# ---------------------------------------------------------------------------
# F1-F3: index_dropbox_files orchestrator tests
# ---------------------------------------------------------------------------


@pytest.fixture
def orchestrator_mocks(monkeypatch):
    """Wire up mocks for index_dropbox_files orchestrator tests."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_connector = MagicMock()
    mock_connector.config = {"_token_encrypted": False}
    mock_connector.last_indexed_at = None
    mock_connector.enable_summary = True

    monkeypatch.setattr(
        _mod,
        "get_connector_by_id",
        AsyncMock(return_value=mock_connector),
    )

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_start = AsyncMock(return_value=MagicMock())
    mock_task_logger.log_task_progress = AsyncMock()
    mock_task_logger.log_task_success = AsyncMock()
    mock_task_logger.log_task_failure = AsyncMock()
    monkeypatch.setattr(
        _mod, "TaskLoggingService", MagicMock(return_value=mock_task_logger)
    )

    monkeypatch.setattr(_mod, "update_connector_last_indexed", AsyncMock())

    full_scan_mock = AsyncMock(return_value=(5, 2, 0))
    monkeypatch.setattr(_mod, "_index_full_scan", full_scan_mock)

    delta_sync_mock = AsyncMock(return_value=(3, 1, 0, "delta-cursor-new"))
    monkeypatch.setattr(_mod, "_index_with_delta_sync", delta_sync_mock)

    mock_client = MagicMock()
    mock_client.get_latest_cursor = AsyncMock(return_value=("latest-cursor-abc", None))
    monkeypatch.setattr(_mod, "DropboxClient", MagicMock(return_value=mock_client))

    return {
        "connector": mock_connector,
        "full_scan_mock": full_scan_mock,
        "delta_sync_mock": delta_sync_mock,
        "mock_client": mock_client,
    }


async def test_orchestrator_uses_delta_sync_when_cursor_and_last_indexed(
    orchestrator_mocks,
):
    """F1: with cursor + last_indexed_at + use_delta_sync, calls delta sync."""
    from datetime import UTC, datetime

    connector = orchestrator_mocks["connector"]
    connector.config = {
        "_token_encrypted": False,
        "folder_cursors": {"/docs": "saved-cursor-123"},
    }
    connector.last_indexed_at = datetime(2026, 1, 1, tzinfo=UTC)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    _indexed, _skipped, error, _unsupported = await index_dropbox_files(
        mock_session,
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        {
            "folders": [{"path": "/docs", "name": "Docs"}],
            "files": [],
            "indexing_options": {"use_delta_sync": True},
        },
    )

    assert error is None
    orchestrator_mocks["delta_sync_mock"].assert_called_once()
    orchestrator_mocks["full_scan_mock"].assert_not_called()


async def test_orchestrator_falls_back_to_full_scan_without_cursor(
    orchestrator_mocks,
):
    """F2: without cursor, falls back to full scan."""
    connector = orchestrator_mocks["connector"]
    connector.config = {"_token_encrypted": False}
    connector.last_indexed_at = None

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    _indexed, _skipped, error, _unsupported = await index_dropbox_files(
        mock_session,
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        {
            "folders": [{"path": "/docs", "name": "Docs"}],
            "files": [],
            "indexing_options": {"use_delta_sync": True},
        },
    )

    assert error is None
    orchestrator_mocks["full_scan_mock"].assert_called_once()
    orchestrator_mocks["delta_sync_mock"].assert_not_called()


async def test_orchestrator_persists_cursor_after_sync(orchestrator_mocks):
    """F3: after sync, persists new cursor to connector config."""
    connector = orchestrator_mocks["connector"]
    connector.config = {"_token_encrypted": False}
    connector.last_indexed_at = None

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    await index_dropbox_files(
        mock_session,
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        {
            "folders": [{"path": "/docs", "name": "Docs"}],
            "files": [],
        },
    )

    assert "folder_cursors" in connector.config
    assert connector.config["folder_cursors"]["/docs"] == "latest-cursor-abc"
