"""Unit tests for page-limit quota gating in Google Drive connector indexer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.unit.connector_indexers.conftest import FakeUser, make_page_limit_session

pytestmark = pytest.mark.unit


# Local aliases for backward compatibility within this module
_FakeUser = FakeUser
_make_page_limit_session = make_page_limit_session


def _make_gdrive_file(file_id: str, name: str, size: int = 80 * 1024) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": "application/octet-stream",
        "size": str(size),
    }


# ---------------------------------------------------------------------------
# Google Drive: _index_selected_files
# ---------------------------------------------------------------------------


@pytest.fixture
def gdrive_selected_mocks(monkeypatch):
    """Mocks for Google Drive _index_selected_files — only system boundaries."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, file_id):
        return get_file_results.get(file_id, (None, f"Not configured: {file_id}"))

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
        "mod": _mod,
        "session": session,
        "fake_user": fake_user,
        "get_file_results": get_file_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_gdrive_selected(mocks, file_ids):
    from app.tasks.connector_indexers.google_drive_indexer import (
        _index_selected_files,
    )

    return await _index_selected_files(
        MagicMock(),
        mocks["session"],
        file_ids,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )


async def test_gdrive_files_within_quota_are_downloaded(gdrive_selected_mocks):
    """Files whose cumulative estimated pages fit within remaining quota
    are sent to _download_and_index."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2", "f3"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (3, 0)

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(
        m, [("f1", "f1.xyz"), ("f2", "f2.xyz"), ("f3", "f3.xyz")]
    )

    assert indexed == 3
    assert errors == []
    call_files = m["download_and_index_mock"].call_args[0][2]
    assert len(call_files) == 3


async def test_gdrive_files_exceeding_quota_rejected(gdrive_selected_mocks):
    """Files whose pages would exceed remaining quota are rejected."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 98
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["big"] = (
        _make_gdrive_file("big", "huge.pdf", size=500 * 1024),
        None,
    )

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(
        m, [("big", "huge.pdf")]
    )

    assert indexed == 0
    assert len(errors) == 1
    assert "page limit" in errors[0].lower()


async def test_gdrive_quota_mix_partial_indexing(gdrive_selected_mocks):
    """3rd file pushes over quota → only first two indexed."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 2

    for fid in ("f1", "f2", "f3"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 0)

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(
        m, [("f1", "f1.xyz"), ("f2", "f2.xyz"), ("f3", "f3.xyz")]
    )

    assert indexed == 2
    assert len(errors) == 1
    call_files = m["download_and_index_mock"].call_args[0][2]
    assert {f["id"] for f in call_files} == {"f1", "f2"}


async def test_gdrive_proportional_page_deduction(gdrive_selected_mocks):
    """Pages deducted are proportional to successfully indexed files."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2", "f3", "f4"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )
    m["download_and_index_mock"].return_value = (2, 2)

    await _run_gdrive_selected(
        m,
        [("f1", "f1.xyz"), ("f2", "f2.xyz"), ("f3", "f3.xyz"), ("f4", "f4.xyz")],
    )

    assert m["fake_user"].pages_used == 2


async def test_gdrive_no_deduction_when_nothing_indexed(gdrive_selected_mocks):
    """If batch_indexed == 0, user's pages_used stays unchanged."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 5
    m["fake_user"].pages_limit = 100

    m["get_file_results"]["f1"] = (
        _make_gdrive_file("f1", "f1.xyz", size=80 * 1024),
        None,
    )
    m["download_and_index_mock"].return_value = (0, 1)

    await _run_gdrive_selected(m, [("f1", "f1.xyz")])

    assert m["fake_user"].pages_used == 5


async def test_gdrive_zero_quota_rejects_all(gdrive_selected_mocks):
    """When pages_used == pages_limit, every file is rejected."""
    m = gdrive_selected_mocks
    m["fake_user"].pages_used = 100
    m["fake_user"].pages_limit = 100

    for fid in ("f1", "f2"):
        m["get_file_results"][fid] = (
            _make_gdrive_file(fid, f"{fid}.xyz", size=80 * 1024),
            None,
        )

    indexed, _skipped, _unsup, errors = await _run_gdrive_selected(
        m, [("f1", "f1.xyz"), ("f2", "f2.xyz")]
    )

    assert indexed == 0
    assert len(errors) == 2


# ---------------------------------------------------------------------------
# Google Drive: _index_full_scan
# ---------------------------------------------------------------------------


@pytest.fixture
def gdrive_full_scan_mocks(monkeypatch):
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    session, fake_user = _make_page_limit_session(0, 100)
    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_mock = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(_mod, "_download_files_parallel", download_mock)

    batch_mock = AsyncMock(return_value=([], 0, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )
    monkeypatch.setattr(
        _mod, "get_user_long_context_llm", AsyncMock(return_value=MagicMock())
    )

    return {
        "mod": _mod,
        "session": session,
        "fake_user": fake_user,
        "task_logger": mock_task_logger,
        "download_mock": download_mock,
        "batch_mock": batch_mock,
    }


async def _run_gdrive_full_scan(mocks, max_files=500):
    from app.tasks.connector_indexers.google_drive_indexer import _index_full_scan

    return await _index_full_scan(
        MagicMock(),
        mocks["session"],
        MagicMock(),
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        "folder-root",
        "My Folder",
        mocks["task_logger"],
        MagicMock(),
        max_files,
        include_subfolders=False,
        enable_summary=True,
    )


async def test_gdrive_full_scan_skips_over_quota(gdrive_full_scan_mocks, monkeypatch):
    m = gdrive_full_scan_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 2

    page_files = [
        _make_gdrive_file(f"f{i}", f"file{i}.xyz", size=80 * 1024) for i in range(5)
    ]
    monkeypatch.setattr(
        m["mod"],
        "get_files_in_folder",
        AsyncMock(return_value=(page_files, None, None)),
    )
    m["download_mock"].return_value = ([], 0)
    m["batch_mock"].return_value = ([], 2, 0)

    _indexed, skipped, _unsup = await _run_gdrive_full_scan(m)

    call_files = m["download_mock"].call_args[0][1]
    assert len(call_files) == 2
    assert skipped == 3


async def test_gdrive_full_scan_deducts_after_indexing(
    gdrive_full_scan_mocks, monkeypatch
):
    m = gdrive_full_scan_mocks
    m["fake_user"].pages_used = 0
    m["fake_user"].pages_limit = 100

    page_files = [
        _make_gdrive_file(f"f{i}", f"file{i}.xyz", size=80 * 1024) for i in range(3)
    ]
    monkeypatch.setattr(
        m["mod"],
        "get_files_in_folder",
        AsyncMock(return_value=(page_files, None, None)),
    )
    mock_docs = [MagicMock() for _ in range(3)]
    m["download_mock"].return_value = (mock_docs, 0)
    m["batch_mock"].return_value = ([], 3, 0)

    await _run_gdrive_full_scan(m)

    assert m["fake_user"].pages_used == 3


# ---------------------------------------------------------------------------
# Google Drive: _index_with_delta_sync
# ---------------------------------------------------------------------------


async def test_gdrive_delta_sync_skips_over_quota(monkeypatch):
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    session, _ = _make_page_limit_session(0, 2)

    changes = [
        {
            "fileId": f"mod{i}",
            "file": _make_gdrive_file(f"mod{i}", f"mod{i}.xyz", size=80 * 1024),
        }
        for i in range(5)
    ]
    monkeypatch.setattr(
        _mod,
        "fetch_all_changes",
        AsyncMock(return_value=(changes, "new-token", None)),
    )
    monkeypatch.setattr(_mod, "categorize_change", lambda change: "modified")
    monkeypatch.setattr(
        _mod, "_should_skip_file", AsyncMock(return_value=(False, None))
    )

    download_mock = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(_mod, "_download_files_parallel", download_mock)

    batch_mock = AsyncMock(return_value=([], 2, 0))
    pipeline_mock = MagicMock()
    pipeline_mock.index_batch_parallel = batch_mock
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod, "IndexingPipelineService", MagicMock(return_value=pipeline_mock)
    )
    monkeypatch.setattr(
        _mod, "get_user_long_context_llm", AsyncMock(return_value=MagicMock())
    )

    mock_task_logger = MagicMock()
    mock_task_logger.log_task_progress = AsyncMock()

    _indexed, skipped, _unsupported = await _mod._index_with_delta_sync(
        MagicMock(),
        session,
        MagicMock(),
        CONNECTOR_ID,
        CONNECTOR_SEARCH_SPACE_ID,
        CONNECTOR_USER_ID,
        "folder-root",
        "start-token",
        mock_task_logger,
        MagicMock(),
        max_files=500,
        enable_summary=True,
    )

    call_files = download_mock.call_args[0][1]
    assert len(call_files) == 2
    assert skipped == 3
