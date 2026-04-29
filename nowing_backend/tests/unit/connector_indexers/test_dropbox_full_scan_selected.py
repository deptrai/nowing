"""Unit tests for Dropbox full-scan and selected-files indexing — D1-D5."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from tests.unit.connector_indexers.conftest import CONNECTOR_USER_ID, CONNECTOR_ID, CONNECTOR_SEARCH_SPACE_ID

from app.tasks.connector_indexers.dropbox_indexer import (
    _index_full_scan,
    _index_selected_files,
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


def _folder_dict(name: str) -> dict:
    return {".tag": "folder", "name": name}


@pytest.fixture
def mock_dropbox_client():
    return MagicMock()


@pytest.fixture
def full_scan_mocks(mock_dropbox_client, monkeypatch):
    """Wire up mocks for _index_full_scan in isolation."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_session = AsyncMock()
    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()
    mock_log_entry = MagicMock()

    skip_results: dict[str, tuple[bool, str | None]] = {}

    monkeypatch.setattr("app.config.config.ETL_SERVICE", "LLAMACLOUD")

    async def _fake_skip(session, file, search_space_id):
        from app.connectors.dropbox.file_types import should_skip_file as _skip

        item_skip, unsup_ext = _skip(file)
        if item_skip:
            if unsup_ext:
                return True, f"unsupported:{unsup_ext}"
            return True, "folder/non-downloadable"
        return skip_results.get(file.get("id", ""), (False, None))

    monkeypatch.setattr(_mod, "_should_skip_file", _fake_skip)

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    from app.services.page_limit_service import PageLimitService as _RealPLS

    mock_page_limit_instance = MagicMock()
    mock_page_limit_instance.get_page_usage = AsyncMock(return_value=(0, 999_999))
    mock_page_limit_instance.update_page_usage = AsyncMock()

    class _MockPageLimitService:
        estimate_pages_from_metadata = staticmethod(
            _RealPLS.estimate_pages_from_metadata
        )

        def __init__(self, session):
            self.get_page_usage = mock_page_limit_instance.get_page_usage
            self.update_page_usage = mock_page_limit_instance.update_page_usage

    monkeypatch.setattr(_mod, "PageLimitService", _MockPageLimitService)

    return {
        "dropbox_client": mock_dropbox_client,
        "session": mock_session,
        "task_logger": mock_task_logger,
        "log_entry": mock_log_entry,
        "skip_results": skip_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_full_scan(mocks, monkeypatch, page_files, *, max_files=500):
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    monkeypatch.setattr(
        _mod,
        "get_files_in_folder",
        AsyncMock(return_value=(page_files, None)),
    )
    return await _index_full_scan(
        mocks["dropbox_client"],
        mocks["session"],
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        "",
        "Root",
        mocks["task_logger"],
        mocks["log_entry"],
        max_files,
        enable_summary=True,
    )


async def test_full_scan_three_phase_counts(full_scan_mocks, monkeypatch):
    """D1: Skipped files excluded, renames counted as indexed, new files downloaded."""
    page_files = [
        _folder_dict("SubFolder"),
        _make_file_dict("skip1", "unchanged.txt"),
        _make_file_dict("rename1", "renamed.txt"),
        _make_file_dict("new1", "new1.txt"),
        _make_file_dict("new2", "new2.txt"),
    ]

    full_scan_mocks["skip_results"]["skip1"] = (True, "unchanged")
    full_scan_mocks["skip_results"]["rename1"] = (
        True,
        "File renamed: 'old' -> 'renamed.txt'",
    )

    full_scan_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped, _unsupported = await _run_full_scan(
        full_scan_mocks, monkeypatch, page_files
    )

    assert indexed == 3  # 1 renamed + 2 from batch
    assert skipped == 2  # 1 folder + 1 unchanged

    call_args = full_scan_mocks["download_and_index_mock"].call_args
    call_files = call_args[0][2]
    assert len(call_files) == 2
    assert {f["id"] for f in call_files} == {"new1", "new2"}


async def test_full_scan_respects_max_files(full_scan_mocks, monkeypatch):
    """D2: Only max_files non-folder items are considered."""
    page_files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(10)]

    full_scan_mocks["download_and_index_mock"].return_value = (3, 0)

    await _run_full_scan(full_scan_mocks, monkeypatch, page_files, max_files=3)

    call_files = full_scan_mocks["download_and_index_mock"].call_args[0][2]
    assert len(call_files) == 3


@pytest.fixture
def selected_files_mocks(mock_dropbox_client, monkeypatch):
    """Wire up mocks for _index_selected_files tests."""
    import app.tasks.connector_indexers.dropbox_indexer as _mod

    mock_session = AsyncMock()

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, path):
        return get_file_results.get(path, (None, f"Not configured: {path}"))

    monkeypatch.setattr(_mod, "get_file_by_path", _fake_get_file)

    skip_results: dict[str, tuple[bool, str | None]] = {}

    async def _fake_skip(session, file, search_space_id):
        return skip_results.get(file["id"], (False, None))

    monkeypatch.setattr(_mod, "_should_skip_file", _fake_skip)

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    from app.services.page_limit_service import PageLimitService as _RealPLS

    mock_page_limit_instance = MagicMock()
    mock_page_limit_instance.get_page_usage = AsyncMock(return_value=(0, 999_999))
    mock_page_limit_instance.update_page_usage = AsyncMock()

    class _MockPageLimitService:
        estimate_pages_from_metadata = staticmethod(
            _RealPLS.estimate_pages_from_metadata
        )

        def __init__(self, session):
            self.get_page_usage = mock_page_limit_instance.get_page_usage
            self.update_page_usage = mock_page_limit_instance.update_page_usage

    monkeypatch.setattr(_mod, "PageLimitService", _MockPageLimitService)

    return {
        "dropbox_client": mock_dropbox_client,
        "session": mock_session,
        "get_file_results": get_file_results,
        "skip_results": skip_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_selected(mocks, file_tuples):
    return await _index_selected_files(
        mocks["dropbox_client"],
        mocks["session"],
        file_tuples,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )


async def test_selected_files_single_file_indexed(selected_files_mocks):
    """D3: Single selected file is downloaded and indexed."""
    selected_files_mocks["get_file_results"]["/report.pdf"] = (
        _make_file_dict("f1", "report.pdf"),
        None,
    )
    selected_files_mocks["download_and_index_mock"].return_value = (1, 0)

    indexed, skipped, _unsupported, errors = await _run_selected(
        selected_files_mocks,
        [("/report.pdf", "report.pdf")],
    )

    assert indexed == 1
    assert skipped == 0
    assert errors == []


async def test_selected_files_fetch_failure_isolation(selected_files_mocks):
    """D4: Fetch failure for one file does not block the others."""
    selected_files_mocks["get_file_results"]["/first.txt"] = (
        _make_file_dict("f1", "first.txt"),
        None,
    )
    selected_files_mocks["get_file_results"]["/mid.txt"] = (None, "HTTP 404")
    selected_files_mocks["get_file_results"]["/third.txt"] = (
        _make_file_dict("f3", "third.txt"),
        None,
    )
    selected_files_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped, _unsupported, errors = await _run_selected(
        selected_files_mocks,
        [
            ("/first.txt", "first.txt"),
            ("/mid.txt", "mid.txt"),
            ("/third.txt", "third.txt"),
        ],
    )

    assert indexed == 2
    assert skipped == 0
    assert len(errors) == 1
    assert "mid.txt" in errors[0]


async def test_selected_files_skip_rename_counting(selected_files_mocks):
    """D5: Skipped files excluded, renames counted as indexed for selected-files mode."""
    for path, fid, fname in [
        ("/unchanged.txt", "s1", "unchanged.txt"),
        ("/renamed.txt", "r1", "renamed.txt"),
        ("/new1.txt", "n1", "new1.txt"),
        ("/new2.txt", "n2", "new2.txt"),
    ]:
        selected_files_mocks["get_file_results"][path] = (
            _make_file_dict(fid, fname),
            None,
        )

    selected_files_mocks["skip_results"]["s1"] = (True, "unchanged")
    selected_files_mocks["skip_results"]["r1"] = (
        True,
        "File renamed: 'old' -> 'renamed.txt'",
    )
    selected_files_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped, _unsupported, errors = await _run_selected(
        selected_files_mocks,
        [
            ("/unchanged.txt", "unchanged.txt"),
            ("/renamed.txt", "renamed.txt"),
            ("/new1.txt", "new1.txt"),
            ("/new2.txt", "new2.txt"),
        ],
    )

    assert indexed == 3  # 1 renamed + 2 batch
    assert skipped == 1
    assert errors == []

    mock = selected_files_mocks["download_and_index_mock"]
    call_files = mock.call_args[0][2]
    assert len(call_files) == 2
    assert {f["id"] for f in call_files} == {"n1", "n2"}
