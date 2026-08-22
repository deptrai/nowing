"""Edge-case tests for ``NowingIngestService.ingest`` status computation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.connectors.exceptions import ConnectorAPIError, ConnectorAuthError
from app.services.chainlens.ingest import NowingIngestService

pytestmark = pytest.mark.unit


def _make_chunk(source_id: str = "src:1") -> dict[str, Any]:
    return {
        "content": "test content",
        "metadata": {
            "sourceId": source_id,
            "domain": "vn_jobs",
            "title": "Data Engineer",
        },
    }


def _fake_config() -> Any:
    import types

    return types.SimpleNamespace(
        CHAINLENS_API_URL="https://chainlens.test",
        CHAINLENS_API_KEY="secret",
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=5,
        CHAINLENS_QUERY_MICROS_PER_CALL=60000,
        CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
        CHAINLENS_INGEST_TIMEOUT_SECONDS=5,
        CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=3,
        CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS=0.0,
    )


@pytest.mark.asyncio
async def test_ingest_no_chunks_returns_noop():
    """An empty chunk list returns a noop result without calling the API."""
    import app.services.chainlens.ingest as ingest_mod

    with patch.object(ingest_mod, "config", _fake_config()):
        service = NowingIngestService()
        result = await service.ingest("batdongsan", [], workspace_id=1)

    assert result.status == "noop"
    assert result.ingest_job_id is None


@pytest.mark.asyncio
async def test_ingest_rejects_overlong_scraper_id():
    """scraper_id over 100 characters is rejected."""
    import app.services.chainlens.ingest as ingest_mod

    with patch.object(ingest_mod, "config", _fake_config()):
        service = NowingIngestService()
        with pytest.raises(ValueError, match="100 character"):
            await service.ingest("x" * 101, [_make_chunk()], workspace_id=1)


@pytest.mark.asyncio
async def test_ingest_multi_batch_creates_parent_job_id(monkeypatch):
    """More than one batch produces a parent job id and uses it as the result id."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"ingestJobId": "child-1"}

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    service = NowingIngestService()
    result = await service.ingest(
        "batdongsan",
        [_make_chunk() for _ in range(1001)],
        workspace_id=1,
    )

    assert result.parent_ingest_job_id is not None
    assert result.parent_ingest_job_id == result.ingest_job_id
    assert len(result.child_ingest_job_ids) == 2


@pytest.mark.asyncio
async def test_ingest_partial_when_noop_and_ingested_mix(monkeypatch):
    """A batch with both noop and ingested source ids is partial."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "ingestJobId": "job-mixed",
            "ingestedSourceIds": ["src:1"],
            "noopSourceIds": ["src:2"],
        }

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    service = NowingIngestService()
    result = await service.ingest(
        "batdongsan",
        [_make_chunk("src:1"), _make_chunk("src:2")],
        workspace_id=1,
    )

    assert result.status == "partial"
    assert result.ingest_job_id == "job-mixed"


@pytest.mark.asyncio
async def test_ingest_falls_back_to_batch_source_ids_when_response_omits_lists(
    monkeypatch,
):
    """If the response omits source id lists, derive them from the batch."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"ingestJobId": "job-bare"}

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    service = NowingIngestService()
    result = await service.ingest(
        "batdongsan",
        [_make_chunk("src:1")],
        workspace_id=1,
    )

    assert result.ingest_job_id == "job-bare"
    assert result.ingested_source_ids == ["src:1"]


@pytest.mark.asyncio
async def test_ingest_breaks_after_auth_error(monkeypatch):
    """ConnectorAuthError stops the batch loop."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    call_count = 0

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        raise ConnectorAuthError("auth failed", service="chainlens_ingest", status_code=403)

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    service = NowingIngestService()
    result = await service.ingest(
        "batdongsan",
        [_make_chunk() for _ in range(10)],
        workspace_id=1,
    )

    assert call_count == 1
    assert result.status == "service_auth_unavailable"


@pytest.mark.asyncio
async def test_ingest_partial_when_one_batch_fails_and_one_succeeds(monkeypatch):
    """Mixed failed/succeeded batches yield partial and an error summary."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    calls: list[int] = []

    fake = _fake_config()
    fake.CHAINLENS_INGEST_MAX_BATCH_SIZE = 1
    monkeypatch.setattr(ingest_mod, "config", fake)

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(len(calls))
        if len(calls) == 1:
            return {"ingestJobId": "child-ok", "ingestedSourceIds": ["src:1"]}
        raise ConnectorAPIError(
            "Bad request",
            service="chainlens_ingest",
            status_code=400,
            response_body={"error": "schema error"},
        )

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    service = NowingIngestService()
    result = await service.ingest(
        "batdongsan",
        [_make_chunk("src:1"), _make_chunk("src:2")],
        workspace_id=1,
    )

    assert result.status == "partial"
    assert result.error is not None
    assert "1 batch(es) failed" in result.error


@pytest.mark.asyncio
async def test_ingest_sets_error_summary_for_failed_batch(monkeypatch):
    """A failed batch sets result.error and dead-letter payload."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise ConnectorAPIError(
            "Bad request",
            service="chainlens_ingest",
            status_code=422,
            response_body={"error": "validation"},
        )

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    session = AsyncMock()
    service = NowingIngestService()
    result = await service.ingest(
        "batdongsan",
        [_make_chunk()],
        workspace_id=1,
        session=session,
    )

    assert result.status == "failed"
    assert result.error is not None
    assert session.add.call_count == 1
    job = session.add.call_args[0][0]
    assert job.dead_letter_payload is not None


@pytest.mark.asyncio
async def test_ingest_success_has_no_error(monkeypatch):
    """A fully successful ingest has no error."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"ingestJobId": "job-ok", "ingestedSourceIds": ["src:1"]}

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    service = NowingIngestService()
    result = await service.ingest("batdongsan", [_make_chunk("src:1")], workspace_id=1)

    assert result.status == "ok"
    assert result.error is None


@pytest.mark.asyncio
async def test_ingest_persists_and_appends_commit_failure_to_error(monkeypatch):
    """If session.commit raises, the error is appended to the result."""
    import app.services.chainlens.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "config", _fake_config())

    async def fake_post_batch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"ingestJobId": "job-ok", "ingestedSourceIds": ["src:1"]}

    monkeypatch.setattr("app.services.chainlens.ingest._post_batch", fake_post_batch)

    session = AsyncMock()
    session.commit.side_effect = RuntimeError("db down")

    service = NowingIngestService()
    result = await service.ingest(
        "batdongsan",
        [_make_chunk("src:1")],
        workspace_id=1,
        session=session,
    )

    assert result.status == "ok"
    assert result.error is not None
    assert "persistence failed" in result.error
