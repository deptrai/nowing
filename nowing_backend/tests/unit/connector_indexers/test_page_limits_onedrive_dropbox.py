"""Unit tests for page-limit quota gating in OneDrive and Dropbox connector indexers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.unit.connector_indexers.conftest import FakeUser, make_page_limit_session

pytestmark = pytest.mark.unit


# Local aliases for backward compatibility within this module
_FakeUser = FakeUser
_make_page_limit_session = make_page_limit_session


# ---------------------------------------------------------------------------
# OneDrive: _index_selected_files
# ---------------------------------------------------------------------------


def _make_onedrive_file(file_id: str, name: str, size: int = 80 * 1024) -> dict:
    return {
        "id": file_id,
        "name": name,
        "file": {"mimeType": "application/octet-stream"},
        "size": str(size),
        "lastModifiedDateTime": "2026-01-01T00:00:00Z",
    }


@pytest.fixture
def onedrive_selected_mocks(monkeypatch):
    import app.tasks.connector_indexers.onedrive_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, file_id):
        return get_file_results.get(file_id, (None, f"Not found: {file_id}"))

    monkeypatch.setattr(_mod, "get_file_by_id", _fake_get_file)
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    pipeline_mock = MagicMock()
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )

    return {
        "session": session,
        "fake_user": fake_user,
        "get_file_results": get_file_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_onedrive_selected(mocks, file_ids):
    from app.tasks.connector_indexers.onedrive_indexer import _index_selected_files

    return await _index_selected_files(
        MagicMock(),
        mocks["session"],
        file_ids,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )


async def test_onedrive_over_quota_rejected(onedrive_selected_mocks):
    """OneDrive: files exceeding quota produce errors, not downloads."""
    m = onedrive_selected_mocks
    m["fake_user"].pages_used = 99
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["big"] = (
        _make_onedrive_file("big", "huge.pdf", size=500 * 1024),
        None,
    )

    indexed, _skipped, _unsup, errors = await _run_onedrive_selected(
        m, [("big", "huge.pdf")]
    )

    assert indexed == 0
    assert len(errors) == 1
    assert "page limit" in errors[0].lower()


async def test_onedrive_deducts_after_success(onedrive_selected_mocks):
    """OneDrive: pages_used increases after successful indexing."""
    m = onedrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2"):
        m["get_file_results"][fid] = (
            _make_onedrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 0)

    await _run_onedrive_selected(m, [("f1", "f1.xyz"), ("f2", "f2.xyz")])

    assert m["fake_user"].pages_used == 2


# ---------------------------------------------------------------------------
# Dropbox: _index_selected_files
# ---------------------------------------------------------------------------


def _make_dropbox_file(file_path: str, name: str, size: int = 80 * 1024) -> dict:
    return {
        "id": f"id:{file_path}",
        "name": name,
        ".tag": "file",
        "path_lower": file_path,
        "size": str(size),
        "server_modified": "2026-01-01T00:00:00Z",
        "content_hash": f"hash_{name}",
    }


@pytest.fixture
def dropbox_selected_mocks(monkeypatch):
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, file_path):
        return get_file_results.get(file_path, (None, f"Not found: {file_path}"))

    monkeypatch.setattr(_mod, "get_file_by_path", _fake_get_file)
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    pipeline_mock = MagicMock()
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )

    return {
        "session": session,
        "fake_user": fake_user,
        "get_file_results": get_file_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_dropbox_selected(mocks, file_paths):
    from app.tasks.connector_indexers.dropbox_indexer import _index_selected_files

    return await _index_selected_files(
        MagicMock(),
        mocks["session"],
        file_paths,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )


async def test_dropbox_over_quota_rejected(dropbox_selected_mocks):
    """Dropbox: files exceeding quota produce errors, not downloads."""
    m = dropbox_selected_mocks
    m["fake_user"].pages_used = 99
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["/huge.pdf"] = (
        _make_dropbox_file("/huge.pdf", "huge.pdf", size=500 * 1024),
        None,
    )

    indexed, _skipped, _unsup, errors = await _run_dropbox_selected(
        m, [("/huge.pdf", "huge.pdf")]
    )

    assert indexed == 0
    assert len(errors) == 1
    assert "page limit" in errors[0].lower()


async def test_dropbox_deducts_after_success(dropbox_selected_mocks):
    """Dropbox: pages_used increases after successful indexing."""
    m = dropbox_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for name in ("f1.xyz", "f2.xyz"):
        path = f"/{name}"
        m["get_file_results"][path] = (
            _make_dropbox_file(path, name, size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 0)

    await _run_dropbox_selected(m, [("/f1.xyz", "f1.xyz"), ("/f2.xyz", "f2.xyz")])

    assert m["fake_user"].pages_used == 2
