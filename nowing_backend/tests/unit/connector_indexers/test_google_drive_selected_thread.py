"""Unit tests for Google Drive selected files + thread parallelism verification."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.unit.connector_indexers.conftest import CONNECTOR_USER_ID, CONNECTOR_ID, CONNECTOR_SEARCH_SPACE_ID

from app.tasks.connector_indexers.google_drive_indexer import (
    _index_selected_files,
)

pytestmark = pytest.mark.unit



def _make_file_dict(file_id: str, name: str, mime: str = "text/plain") -> dict:
    return {"id": file_id, "name": name, "mimeType": mime}


def _mock_extract_ok(file_id: str, file_name: str):
    return (
        f"# Content of {file_name}",
        {"google_drive_file_id": file_id, "google_drive_file_name": file_name},
        None,
    )


def _make_page_limit_session(pages_used=0, pages_limit=999_999):
    class _FakeUser:
        def __init__(self, pu, pl):
            self.pages_used = pu
            self.pages_limit = pl

    fake_user = _FakeUser(pages_used, pages_limit)
    session = AsyncMock()

    def _make_result(*_a, **_kw):
        r = MagicMock()
        r.first.return_value = (fake_user.pages_used, fake_user.pages_limit)
        r.unique.return_value.scalar_one_or_none.return_value = fake_user
        return r

    session.execute = AsyncMock(side_effect=_make_result)
    return session, fake_user


@pytest.fixture
def mock_drive_client():
    return MagicMock()


@pytest.fixture
def selected_files_mocks(mock_drive_client, monkeypatch):
    """Wire up mocks for _index_selected_files tests."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    mock_session, _ = _make_page_limit_session()

    get_file_results: dict[str, tuple[dict | None, str | None]] = {}

    async def _fake_get_file(client, file_id):
        return get_file_results.get(file_id, (None, f"Not configured: {file_id}"))

    monkeypatch.setattr(_mod, "get_file_by_id", _fake_get_file)

    skip_results: dict[str, tuple[bool, str | None]] = {}

    async def _fake_skip(session, file, search_space_id):
        return skip_results.get(file["id"], (False, None))

    monkeypatch.setattr(_mod, "_should_skip_file", _fake_skip)

    download_and_index_mock = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(_mod, "_download_and_index", download_and_index_mock)

    pipeline_mock = MagicMock()
    pipeline_mock.create_placeholder_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(
        _mod,
        "IndexingPipelineService",
        MagicMock(return_value=pipeline_mock),
    )

    return {
        "drive_client": mock_drive_client,
        "session": mock_session,
        "get_file_results": get_file_results,
        "skip_results": skip_results,
        "download_and_index_mock": download_and_index_mock,
    }


async def _run_selected(mocks, file_ids):
    return await _index_selected_files(
        mocks["drive_client"],
        mocks["session"],
        file_ids,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )


async def test_selected_files_single_file_indexed(selected_files_mocks):
    """Tracer bullet: one file fetched, not skipped, indexed via parallel pipeline."""
    selected_files_mocks["get_file_results"]["f1"] = (
        _make_file_dict("f1", "report.pdf"),
        None,
    )
    selected_files_mocks["download_and_index_mock"].return_value = (1, 0)

    indexed, skipped, _unsup, errors = await _run_selected(
        selected_files_mocks,
        [("f1", "report.pdf")],
    )

    assert indexed == 1
    assert skipped == 0
    assert errors == []
    selected_files_mocks["download_and_index_mock"].assert_called_once()


async def test_selected_files_fetch_failure_isolation(selected_files_mocks):
    """get_file_by_id failing for one file collects an error; others still indexed."""
    selected_files_mocks["get_file_results"]["f1"] = (
        _make_file_dict("f1", "first.txt"),
        None,
    )
    selected_files_mocks["get_file_results"]["f2"] = (None, "HTTP 404")
    selected_files_mocks["get_file_results"]["f3"] = (
        _make_file_dict("f3", "third.txt"),
        None,
    )
    selected_files_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped, _unsup, errors = await _run_selected(
        selected_files_mocks,
        [("f1", "first.txt"), ("f2", "mid.txt"), ("f3", "third.txt")],
    )

    assert indexed == 2
    assert skipped == 0
    assert len(errors) == 1
    assert "mid.txt" in errors[0]
    assert "HTTP 404" in errors[0]


async def test_selected_files_skip_rename_counting(selected_files_mocks):
    """Unchanged files are skipped, renames counted as indexed,
    and only new files are sent to _download_and_index."""
    for fid, fname in [
        ("s1", "unchanged.txt"),
        ("r1", "renamed.txt"),
        ("n1", "new1.txt"),
        ("n2", "new2.txt"),
    ]:
        selected_files_mocks["get_file_results"][fid] = (
            _make_file_dict(fid, fname),
            None,
        )

    selected_files_mocks["skip_results"]["s1"] = (True, "unchanged")
    selected_files_mocks["skip_results"]["r1"] = (
        True,
        "File renamed: 'old' → 'renamed.txt'",
    )

    selected_files_mocks["download_and_index_mock"].return_value = (2, 0)

    indexed, skipped, _unsup, errors = await _run_selected(
        selected_files_mocks,
        [
            ("s1", "unchanged.txt"),
            ("r1", "renamed.txt"),
            ("n1", "new1.txt"),
            ("n2", "new2.txt"),
        ],
    )

    assert indexed == 3  # 1 renamed + 2 batch
    assert skipped == 1  # 1 unchanged
    assert errors == []

    mock = selected_files_mocks["download_and_index_mock"]
    mock.assert_called_once()
    call_files = (
        mock.call_args[1].get("files")
        if "files" in (mock.call_args[1] or {})
        else mock.call_args[0][2]
    )
    assert len(call_files) == 2
    assert {f["id"] for f in call_files} == {"n1", "n2"}


# ---------------------------------------------------------------------------
# asyncio.to_thread verification — prove blocking calls run in parallel
# ---------------------------------------------------------------------------


async def test_client_download_file_runs_in_thread_parallel():
    """Calling download_file concurrently via asyncio.gather should overlap
    blocking work on separate threads, proving to_thread is effective.

    Strategy: use a `threading.Barrier(3, timeout=2)` — if the 3 concurrent
    calls don't all run in separate threads at the same time, the barrier
    times out and raises `threading.BrokenBarrierError`. This is a
    **deterministic** proof of parallelism (no wall-clock tolerance).
    """
    import threading
    from app.connectors.google_drive.client import GoogleDriveClient

    num_calls = 3
    barrier = threading.Barrier(num_calls, timeout=2.0)

    def _blocking_download(service, file_id, credentials):
        # If thread pool is single-threaded (no parallelism), barrier will
        # time out and raise BrokenBarrierError — failing the test.
        barrier.wait()
        return b"fake-content", None

    client = GoogleDriveClient.__new__(GoogleDriveClient)
    client.service = MagicMock()
    client._resolved_credentials = MagicMock()
    client._service_lock = asyncio.Lock()

    with patch.object(
        GoogleDriveClient,
        "_sync_download_file",
        staticmethod(_blocking_download),
    ):
        results = await asyncio.gather(
            *(client.download_file(f"file-{i}") for i in range(num_calls))
        )

    for content, error in results:
        assert content == b"fake-content"
        assert error is None


async def test_client_export_google_file_runs_in_thread_parallel():
    """Same strategy for export_google_file — verify to_thread parallelism.

    Uses `threading.Barrier` for deterministic proof (no timing tolerance).
    """
    import threading
    from app.connectors.google_drive.client import GoogleDriveClient

    num_calls = 3
    barrier = threading.Barrier(num_calls, timeout=2.0)

    def _blocking_export(service, file_id, mime_type, credentials):
        barrier.wait()
        return b"exported", None

    client = GoogleDriveClient.__new__(GoogleDriveClient)
    client.service = MagicMock()
    client._resolved_credentials = MagicMock()
    client._service_lock = asyncio.Lock()

    with patch.object(
        GoogleDriveClient,
        "_sync_export_google_file",
        staticmethod(_blocking_export),
    ):
        results = await asyncio.gather(
            *(
                client.export_google_file(f"file-{i}", "application/pdf")
                for i in range(num_calls)
            )
        )

    for content, error in results:
        assert content == b"exported"
        assert error is None
