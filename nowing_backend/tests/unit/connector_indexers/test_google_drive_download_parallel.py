"""Unit tests for Google Drive parallel download (_download_files_parallel) — Slices 1-5."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from tests.unit.connector_indexers.conftest import CONNECTOR_USER_ID, CONNECTOR_ID, CONNECTOR_SEARCH_SPACE_ID

from app.tasks.connector_indexers.google_drive_indexer import (
    _download_files_parallel,
)

pytestmark = pytest.mark.unit



def _make_file_dict(file_id: str, name: str, mime: str = "text/plain") -> dict:
    return {"id": file_id, "name": name, "mimeType": mime}


def _mock_extract_ok(file_id: str, file_name: str):
    """Return a successful (markdown, metadata, None) tuple."""
    return (
        f"# Content of {file_name}",
        {"google_drive_file_id": file_id, "google_drive_file_name": file_name},
        None,
    )


@pytest.fixture
def mock_drive_client():
    return MagicMock()


@pytest.fixture
def patch_extract(monkeypatch):
    """Provide a helper to set the download_and_extract_content mock."""

    def _patch(side_effect=None, return_value=None):
        mock = AsyncMock(side_effect=side_effect, return_value=return_value)
        monkeypatch.setattr(
            "app.tasks.connector_indexers.google_drive_indexer.download_and_extract_content",
            mock,
        )
        return mock

    return _patch


async def test_single_file_returns_one_connector_document(
    mock_drive_client,
    patch_extract,
):
    """Tracer bullet: downloading one file produces one ConnectorDocument."""
    patch_extract(return_value=_mock_extract_ok("f1", "test.txt"))

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        [_make_file_dict("f1", "test.txt")],
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 1
    assert failed == 0
    assert docs[0].title == "test.txt"
    assert docs[0].unique_id == "f1"


async def test_multiple_files_all_produce_documents(
    mock_drive_client,
    patch_extract,
):
    """All files are downloaded and converted to ConnectorDocuments."""
    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]
    patch_extract(
        side_effect=[_mock_extract_ok(f"f{i}", f"file{i}.txt") for i in range(3)]
    )

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 3
    assert failed == 0
    assert {d.unique_id for d in docs} == {"f0", "f1", "f2"}


async def test_one_download_exception_does_not_block_others(
    mock_drive_client,
    patch_extract,
):
    """A RuntimeError in one download still lets the other files succeed."""
    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]
    patch_extract(
        side_effect=[
            _mock_extract_ok("f0", "file0.txt"),
            RuntimeError("network timeout"),
            _mock_extract_ok("f2", "file2.txt"),
        ]
    )

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 2
    assert failed == 1
    assert {d.unique_id for d in docs} == {"f0", "f2"}


async def test_etl_error_counts_as_download_failure(
    mock_drive_client,
    patch_extract,
):
    """download_and_extract_content returning an error is counted as failed."""
    files = [_make_file_dict("f0", "good.txt"), _make_file_dict("f1", "bad.txt")]
    patch_extract(
        side_effect=[
            _mock_extract_ok("f0", "good.txt"),
            (None, {}, "ETL failed"),
        ]
    )

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
    )

    assert len(docs) == 1
    assert failed == 1


async def test_concurrency_bounded_by_semaphore(
    mock_drive_client,
    monkeypatch,
):
    """Peak concurrent downloads never exceeds max_concurrency."""
    lock = asyncio.Lock()
    active = 0
    peak = 0

    async def _slow_extract(client, file, **kwargs):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.005)
        async with lock:
            active -= 1
        fid = file["id"]
        return _mock_extract_ok(fid, file["name"])

    monkeypatch.setattr(
        "app.tasks.connector_indexers.google_drive_indexer.download_and_extract_content",
        _slow_extract,
    )

    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(6)]

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
        max_concurrency=2,
    )

    assert len(docs) == 6
    assert failed == 0
    assert peak <= 2, f"Peak concurrency was {peak}, expected <= 2"


async def test_heartbeat_fires_during_parallel_downloads(
    mock_drive_client,
    monkeypatch,
):
    """on_heartbeat is called at least once when downloads take time."""
    import app.tasks.connector_indexers.google_drive_indexer as _mod

    monkeypatch.setattr(_mod, "HEARTBEAT_INTERVAL_SECONDS", 0)

    async def _slow_extract(client, file, **kwargs):
        await asyncio.sleep(0.005)
        return _mock_extract_ok(file["id"], file["name"])

    monkeypatch.setattr(
        "app.tasks.connector_indexers.google_drive_indexer.download_and_extract_content",
        _slow_extract,
    )

    heartbeat_calls: list[int] = []

    async def _on_heartbeat(count: int):
        heartbeat_calls.append(count)

    files = [_make_file_dict(f"f{i}", f"file{i}.txt") for i in range(3)]

    docs, failed = await _download_files_parallel(
        mock_drive_client,
        files,
        connector_id=CONNECTOR_ID,
        search_space_id=CONNECTOR_SEARCH_SPACE_ID,
        user_id=CONNECTOR_USER_ID,
        enable_summary=True,
        on_heartbeat=_on_heartbeat,
    )

    assert len(docs) == 3
    assert failed == 0
    assert len(heartbeat_calls) >= 1, "Heartbeat should have fired at least once"
