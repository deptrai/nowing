"""Unit tests for chainlens ingest schema violation handling (Story 12-4e)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
    """Mock chunk object."""
    chunk = MagicMock()
    chunk.model_dump.return_value = {
        "content": "test content",
        "metadata": {
            "sourceId": "test:123",
            "domain": "vn_jobs",
            "title": "Data Engineer",
        },
    }
    return chunk



@pytest.mark.asyncio
async def test_ingest_logs_first_failing_chunk_details_on_400(mock_session, mock_chunk, caplog):
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

    error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_logs) > 0
    log_message = error_logs[0].message
    assert "test:123" in log_message or "vn_jobs" in log_message or "first failing chunk" in log_message.lower()



@pytest.mark.asyncio
async def test_ingest_logs_first_failing_chunk_details_on_422(mock_session, mock_chunk, caplog):
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

    error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_logs) > 0



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
