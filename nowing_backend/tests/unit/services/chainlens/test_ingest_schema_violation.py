"""Unit tests for chainlens ingest schema violation handling (Story 12-4e)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.connectors.exceptions import ConnectorAPIError
from app.services.chainlens.ingest import NowingIngestService

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_session():
    """Mock async session."""
    return AsyncMock()


@pytest.fixture
def mock_chunk():
    """Return a chunk dict matching the canonical Chunk shape."""
    return {
        "content": "test content",
        "metadata": {
            "sourceId": "test:123",
            "domain": "vn_jobs",
            "title": "Data Engineer",
        },
    }


def _find_schema_violation_log(caplog):
    """Return the first ERROR log about schema violations."""
    for record in caplog.records:
        if record.levelname == "ERROR" and "schema violation" in record.message.lower():
            return record
    return None


@pytest.mark.asyncio
async def test_ingest_logs_first_failing_chunk_details_on_400(
    mock_session, mock_chunk, caplog
):
    """NowingIngestService.ingest() logs first failing chunk details on 400."""
    service = NowingIngestService()

    async def fake_post_batch(*args, **kwargs):
        raise ConnectorAPIError(
            "Bad request",
            service="chainlens_ingest",
            status_code=400,
            response_body={"error": "Invalid schema"},
        )

    with (
        patch("app.services.chainlens.ingest._post_batch", fake_post_batch),
        patch("app.services.chainlens.ingest.ChainLensServiceAuth") as mock_auth,
        caplog.at_level("ERROR"),
    ):
        mock_auth.return_value.configured = True
        await service.ingest(
            scraper_id="vn_jobs.aggregate",
            chunks=[mock_chunk],
            workspace_id=1,
            session=mock_session,
        )

    log = _find_schema_violation_log(caplog)
    assert log is not None
    assert "test:123" in log.getMessage()
    assert "vn_jobs" in log.getMessage()
    assert "Data Engineer" in log.getMessage()


@pytest.mark.asyncio
async def test_ingest_logs_first_failing_chunk_details_on_422(
    mock_session, mock_chunk, caplog
):
    """NowingIngestService.ingest() logs first failing chunk details on 422."""
    service = NowingIngestService()

    async def fake_post_batch(*args, **kwargs):
        raise ConnectorAPIError(
            "Unprocessable entity",
            service="chainlens_ingest",
            status_code=422,
            response_body={"error": "Validation failed"},
        )

    with (
        patch("app.services.chainlens.ingest._post_batch", fake_post_batch),
        patch("app.services.chainlens.ingest.ChainLensServiceAuth") as mock_auth,
        caplog.at_level("ERROR"),
    ):
        mock_auth.return_value.configured = True
        await service.ingest(
            scraper_id="vn_jobs.aggregate",
            chunks=[mock_chunk],
            workspace_id=1,
            session=mock_session,
        )

    log = _find_schema_violation_log(caplog)
    assert log is not None
    assert "test:123" in log.getMessage()
    assert "Validation failed" in log.getMessage()


@pytest.mark.asyncio
async def test_ingest_batch_marked_failed_not_retried_for_400(mock_session, mock_chunk):
    """Batch is marked failed and not retried for 400."""
    service = NowingIngestService()

    call_count = 0

    async def fake_post_batch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise ConnectorAPIError(
            "Bad request",
            service="chainlens_ingest",
            status_code=400,
            response_body={"error": "Invalid schema"},
        )

    with (
        patch("app.services.chainlens.ingest._post_batch", fake_post_batch),
        patch("app.services.chainlens.ingest.ChainLensServiceAuth") as mock_auth,
    ):
        mock_auth.return_value.configured = True
        result = await service.ingest(
            scraper_id="vn_jobs.aggregate",
            chunks=[mock_chunk],
            workspace_id=1,
            session=mock_session,
        )

    assert call_count == 1
    assert result.status == "failed"
    assert result.error is not None


@pytest.mark.asyncio
async def test_ingest_409_conflict_treated_as_noop(mock_session, mock_chunk):
    """409 conflict is treated as idempotent noop, not failed."""
    service = NowingIngestService()

    async def fake_post_batch(*args, **kwargs):
        raise ConnectorAPIError(
            "Conflict",
            service="chainlens_ingest",
            status_code=409,
            response_body={
                "ingestJobId": "job-409",
                "noopSourceIds": ["test:123"],
            },
        )

    with (
        patch("app.services.chainlens.ingest._post_batch", fake_post_batch),
        patch("app.services.chainlens.ingest.ChainLensServiceAuth") as mock_auth,
    ):
        mock_auth.return_value.configured = True
        result = await service.ingest(
            scraper_id="vn_jobs.aggregate",
            chunks=[mock_chunk],
            workspace_id=1,
            session=mock_session,
        )

    assert result.status == "noop"
    assert result.ingest_job_id == "job-409"
    assert result.noop_source_ids == ["test:123"]
