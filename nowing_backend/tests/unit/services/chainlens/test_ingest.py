"""Unit tests for ``app.services.chainlens.ingest``."""

from __future__ import annotations

import types
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

pytestmark = pytest.mark.unit


def _make_chunks(count: int) -> list[Any]:
    from app.services.scraper_chunks.schemas import Chunk, ChunkMetadata

    base = {
        "source": "nowing_scraper",
        "sourceId": "src",
        "domain": "bds",
        "fetchedAt": "2026-08-11T00:00:00+00:00",
        "contentType": "listing",
    }
    chunks: list[Any] = []
    for i in range(count):
        metadata = dict(base)
        metadata["sourceId"] = f"chunk:{i:04d}"
        chunks.append(Chunk(content=f"content {i}", metadata=ChunkMetadata(**metadata)))
    return chunks


def _httpx_client_class(calls: list[dict[str, Any]], responses: list[Any]):
    """Return a fake httpx.AsyncClient class that replays a list of responses."""

    class _FakeResponse:
        def __init__(self, status_code: int, json_data: dict[str, Any] | None = None):
            self.status_code = status_code
            self._json = json_data or {}
            self.content = b""
            self.text = ""

        def json(self) -> dict[str, Any]:
            return self._json

    class _FakeClient:
        def __init__(self, **kwargs: Any):
            self._client_kwargs = kwargs

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            calls.append({"url": url, "kwargs": kwargs})
            if not responses:
                return _FakeResponse(500)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            status_code, json_data = item
            return _FakeResponse(status_code, json_data)

    return _FakeClient


def _fake_config() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        CHAINLENS_API_URL="https://chainlens.test",
        CHAINLENS_API_KEY="secret",
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=5,
        CHAINLENS_QUERY_MICROS_PER_CALL=60000,
        CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
        CHAINLENS_INGEST_TIMEOUT_SECONDS=5,
        CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=3,
    )


@pytest.mark.skip(reason="ATDD red phase: implement Story 20.1")
@pytest.mark.asyncio
async def test_ingest_calls_post_ingest_scraper_with_auth_and_workspace(
    monkeypatch,
):
    """NowingIngestService.ingest posts the batch with Bearer auth and workspace context."""
    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    calls: list[dict[str, Any]] = []
    responses = [(200, {"ingestJobId": "job-123"})]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = NowingIngestService()
    result = await service.ingest(
        scraper_id="batdongsan",
        chunks=_make_chunks(2),
        workspace_id=42,
    )

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://chainlens.test/v1/ingest/scraper"
    assert call["kwargs"]["headers"]["Authorization"] == "Bearer secret"
    body = call["kwargs"]["json"]
    assert body["scraper_id"] == "batdongsan"
    assert body["workspace_id"] == 42
    assert body["source"] == "nowing_scraper"
    assert len(body["chunks"]) == 2
    assert result.ingest_job_id == "job-123"


@pytest.mark.skip(reason="ATDD red phase: implement Story 20.1")
@pytest.mark.asyncio
async def test_ingest_returns_ingest_job_id_and_persists_mapping(monkeypatch):
    """A successful 200 returns ingestJobId and the Postgres mapping is committed."""
    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    calls: list[dict[str, Any]] = []
    responses = [(200, {"ingestJobId": "job-persist"})]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    session = AsyncMock()
    service = NowingIngestService()
    result = await service.ingest(
        scraper_id="batdongsan",
        chunks=_make_chunks(1),
        workspace_id=42,
        session=session,
    )

    assert result.ingest_job_id == "job-persist"
    assert session.commit.await_count >= 1


@pytest.mark.skip(reason="ATDD red phase: implement Story 20.1")
@pytest.mark.asyncio
async def test_ingest_paginates_batches_larger_than_1000(monkeypatch):
    """More than 1,000 chunks is split into multiple POST calls with a parent job id."""
    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService

    fake = _fake_config()
    fake.CHAINLENS_INGEST_MAX_BATCH_SIZE = 1000
    monkeypatch.setattr(ingest_mod, "config", fake)

    calls: list[dict[str, Any]] = []
    responses = [
        (200, {"ingestJobId": "child-1"}),
        (200, {"ingestJobId": "child-2"}),
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = NowingIngestService()
    result = await service.ingest(
        scraper_id="batdongsan",
        chunks=_make_chunks(1001),
        workspace_id=1,
    )

    assert len(calls) == 2
    assert result.parent_ingest_job_id is not None
    assert result.child_ingest_job_ids == ["child-1", "child-2"]


@pytest.mark.skip(reason="ATDD red phase: implement Story 20.1")
@pytest.mark.asyncio
async def test_ingest_maps_409_duplicate_source_id_to_noop(monkeypatch):
    """A 409 response maps duplicate sourceIds to noop and ingests the rest."""
    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    calls: list[dict[str, Any]] = []
    responses = [
        (
            409,
            {
                "noop_source_ids": ["chunk:0001"],
                "ingested_source_ids": ["chunk:0002"],
            },
        )
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = NowingIngestService()
    result = await service.ingest(
        scraper_id="batdongsan",
        chunks=_make_chunks(2),
        workspace_id=1,
    )

    assert "chunk:0001" in result.noop_source_ids
    assert "chunk:0002" in result.ingested_source_ids


@pytest.mark.skip(reason="ATDD red phase: implement Story 20.1")
@pytest.mark.asyncio
async def test_ingest_retries_5xx_with_exponential_backoff(monkeypatch):
    """5xx responses trigger up to 3 attempts and eventually succeed."""
    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    calls: list[dict[str, Any]] = []
    responses = [
        (503, {}),
        (503, {}),
        (200, {"ingestJobId": "job-recovered"}),
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = NowingIngestService()
    result = await service.ingest(
        scraper_id="batdongsan",
        chunks=_make_chunks(1),
        workspace_id=1,
    )

    assert len(calls) == 3
    assert result.ingest_job_id == "job-recovered"


@pytest.mark.skip(reason="ATDD red phase: implement Story 20.1")
@pytest.mark.asyncio
async def test_ingest_emits_failed_metric_after_max_retries(monkeypatch):
    """After max retries the job is failed, dead-lettered, and a metric is emitted."""
    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    metric_calls: list[dict[str, Any]] = []
    fake_metrics = types.SimpleNamespace(
        record_chainlens_ingest_failed=lambda **kwargs: metric_calls.append(kwargs)
    )
    monkeypatch.setattr(ingest_mod, "metrics", fake_metrics)

    calls: list[dict[str, Any]] = []
    responses = [(500, {}), (500, {}), (500, {})]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = NowingIngestService()
    result = await service.ingest(
        scraper_id="batdongsan",
        chunks=_make_chunks(1),
        workspace_id=1,
    )

    assert len(calls) == 3
    assert result.status == "failed"
    assert len(metric_calls) == 1


@pytest.mark.skip(reason="ATDD red phase: implement Story 20.1")
@pytest.mark.asyncio
async def test_ingest_retries_timeout(monkeypatch):
    """Network timeouts are retried up to the max attempt limit."""
    import app.services.chainlens.ingest as ingest_mod
    from app.services.chainlens.ingest import NowingIngestService

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    calls: list[dict[str, Any]] = []
    responses = [
        httpx.TimeoutException("timeout"),
        httpx.TimeoutException("timeout"),
        (200, {"ingestJobId": "job-timeout-recovered"}),
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = NowingIngestService()
    result = await service.ingest(
        scraper_id="batdongsan",
        chunks=_make_chunks(1),
        workspace_id=1,
    )

    assert len(calls) == 3
    assert result.ingest_job_id == "job-timeout-recovered"
