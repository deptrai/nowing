"""Unit tests for ``_persist_jobs_aggregates`` in the jobs aggregator orchestrator."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
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
    listing._source_record_ids = {"vietnamworks": "vw:123"}

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
    listing._source_record_ids = {"vietnamworks": "vw:123"}

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
    listing._source_record_ids = {"vietnamworks": "vw:123"}

    status, message = await _persist_jobs_aggregates(SimpleNamespace(), 1, [listing])

    assert status == "not_attempted"
    assert message is None


async def test_persist_ok_when_all_sources_succeed(
    session, sample_listing, monkeypatch
):
    """Successful persistence of all sources returns 'ok' and no message."""
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator.upsert_canonical_entity",
        AsyncMock(return_value=None),
    )
    stage = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._stage_jobs_persist_outbox", stage
    )

    status, message = await _persist_jobs_aggregates(session, 1, [sample_listing])

    assert status == "ok"
    assert message is None
    assert stage.call_count == 0


async def test_persist_partial_when_one_source_fails(
    session, sample_listing, monkeypatch
):
    """A listing with at least one failed source but also one success is 'partial'."""
    sample_listing._source_record_ids = {"vietnamworks": "vw:123", "topcv": "tc:456"}
    sample_listing._source_url_map = {
        "vietnamworks": "https://vietnamworks.com/123",
        "topcv": "https://topcv.com/456",
    }

    async def fake_upsert(session, **kwargs: Any) -> None:
        if kwargs.get("source_name") == "topcv":
            raise RuntimeError("topcv persist failed")

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator.upsert_canonical_entity",
        fake_upsert,
    )
    stage = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._stage_jobs_persist_outbox", stage
    )

    status, message = await _persist_jobs_aggregates(session, 1, [sample_listing])

    assert status == "partial"
    assert message is not None
    assert stage.call_count == 1


async def test_persist_failed_when_all_sources_fail(
    session, sample_listing, monkeypatch
):
    """If every source fails for every listing, return 'failed' and the first error."""
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator.upsert_canonical_entity",
        AsyncMock(side_effect=RuntimeError("persist failed")),
    )
    stage = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._stage_jobs_persist_outbox", stage
    )

    status, message = await _persist_jobs_aggregates(session, 1, [sample_listing])

    assert status == "failed"
    assert "persist failed" in message
    assert stage.call_count == 1


async def test_persist_stages_outbox_for_each_failed_listing(
    session, sample_listing, monkeypatch
):
    """A failed listing triggers _stage_jobs_persist_outbox with its error."""
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator.upsert_canonical_entity",
        AsyncMock(side_effect=RuntimeError("listing failed")),
    )
    stage = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._stage_jobs_persist_outbox", stage
    )

    await _persist_jobs_aggregates(session, 1, [sample_listing])

    assert stage.call_count == 1
    call_args = stage.call_args[0]
    assert call_args[1] == 1  # workspace_id
    assert call_args[2] == sample_listing  # listing
    assert "listing failed" in call_args[3]  # error


async def test_persist_logs_when_outbox_also_fails(
    session, sample_listing, monkeypatch, caplog
):
    """If _stage_jobs_persist_outbox also raises, it is logged and the run continues."""
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator.upsert_canonical_entity",
        AsyncMock(side_effect=RuntimeError("listing failed")),
    )
    stage = AsyncMock(side_effect=RuntimeError("outbox failed"))
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._stage_jobs_persist_outbox", stage
    )

    with caplog.at_level("ERROR"):
        status, _ = await _persist_jobs_aggregates(session, 1, [sample_listing])

    assert status == "failed"
    assert any("outbox" in record.message for record in caplog.records)
