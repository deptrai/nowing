"""Unit tests for ``_persist_jobs_aggregates`` in the jobs aggregator orchestrator."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.jobs_aggregator.orchestrator import _persist_jobs_aggregates
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing

pytestmark = pytest.mark.unit


class _FakeAsyncSession(AsyncSession):
    """A minimal AsyncSession subclass so ``isinstance`` is true."""


@pytest.fixture
def session() -> AsyncSession:
    return _FakeAsyncSession()  # type: ignore[return-value]


@pytest.fixture
def sample_listing() -> VnJobAggregatedListing:
    listing = VnJobAggregatedListing(
        id="vw:123",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="We are hiring.",
        job_requirement="Python, SQL.",
        confidence_score=0.7,
    )
    listing._source_record_ids = {"vietnamworks": "vw:123"}
    listing._source_url_map = {"vietnamworks": "https://vietnamworks.com/123"}
    return listing


async def test_persist_not_attempted_without_session():
    """If session is None, persist is not attempted."""
    listing = VnJobAggregatedListing(
        id="vw:123",
        title="Data Engineer",
        company="FPT",
        source="vietnamworks",
    )

    status, message = await _persist_jobs_aggregates(None, 1, [listing])

    assert status == "not_attempted"
    assert message is None


async def test_persist_not_attempted_without_workspace_id(session):
    """If workspace_id is None, persist is not attempted."""
    listing = VnJobAggregatedListing(
        id="vw:123",
        title="Data Engineer",
        company="FPT",
        source="vietnamworks",
    )

    status, message = await _persist_jobs_aggregates(session, None, [listing])

    assert status == "not_attempted"
    assert message is None


async def test_persist_not_attempted_with_non_async_session():
    """If session is not an AsyncSession, persist is not attempted."""
    listing = VnJobAggregatedListing(
        id="vw:123",
        title="Data Engineer",
        company="FPT",
        source="vietnamworks",
    )

    status, message = await _persist_jobs_aggregates(SimpleNamespace(), 1, [listing])

    assert status == "not_attempted"
    assert message is None


async def test_persist_ok_when_ingest_succeeds(
    session, sample_listing, monkeypatch
):
    """Successful chainlens ingest returns 'ok' and no message."""
    monkeypatch.setattr(
        "app.services.chainlens.ingest.NowingIngestService.ingest",
        AsyncMock(return_value=SimpleNamespace(status="ok", error=None)),
    )

    status, message = await _persist_jobs_aggregates(session, 1, [sample_listing])

    assert status == "ok"
    assert message is None


async def test_persist_failed_when_ingest_fails(
    session, sample_listing, monkeypatch
):
    """If chainlens ingest fails, return 'failed' and the error."""
    monkeypatch.setattr(
        "app.services.chainlens.ingest.NowingIngestService.ingest",
        AsyncMock(side_effect=RuntimeError("ingest failed")),
    )

    status, message = await _persist_jobs_aggregates(session, 1, [sample_listing])

    assert status == "failed"
    assert "ingest failed" in message


async def test_persist_ok_when_no_listings(session):
    status, message = await _persist_jobs_aggregates(session, 1, [])
    assert status == "ok"
    assert message is None
