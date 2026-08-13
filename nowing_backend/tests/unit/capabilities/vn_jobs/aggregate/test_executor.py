"""Unit tests for the ``vn_jobs.aggregate`` executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.core.types import CapabilityContext
from app.capabilities.vn_jobs.aggregate.executor import build_aggregate_executor
from app.capabilities.vn_jobs.aggregate.schemas import (
    VnJobAggregateInput,
    VnJobAggregateOutput,
)
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing

pytestmark = pytest.mark.unit


def _make_context() -> CapabilityContext:
    """Return a minimal capability context for tests."""
    from types import SimpleNamespace

    return SimpleNamespace(session=AsyncMock(), workspace_id=42, run_id="run-123")  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_executor_returns_output_without_items():
    """When aggregator returns no items, ingest_status is set to noop."""
    execute = build_aggregate_executor()

    with patch(
        "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
        new=AsyncMock(return_value=VnJobAggregateOutput()),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), _make_context())

    assert output.total_items == 0
    assert output.ingest_status is None


@pytest.mark.asyncio
async def test_executor_ingests_items_and_sets_ingest_fields():
    """When aggregator returns items, executor ingests and sets ingest fields."""
    execute = build_aggregate_executor()

    listing = VnJobAggregatedListing(
        id="vw:1",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Build data pipelines.",
        job_requirement="Python.",
        confidence_score=0.9,
    )
    aggregate_output = VnJobAggregateOutput(items=[listing])

    class _FakeIngestResult:
        ingest_job_id = "job-abc"
        parent_ingest_job_id = None
        ingested_source_ids = ["vw:1"]
        noop_source_ids = []
        status = "ok"

    with (
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
            new=AsyncMock(return_value=aggregate_output),
        ),
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.NowingIngestService",
            return_value=AsyncMock(
                ingest=AsyncMock(return_value=_FakeIngestResult())
            ),
        ),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), _make_context())

    assert output.ingest_job_id == "job-abc"
    assert output.ingest_status == "ok"
    assert output.ingested_count == 1
    assert output.noop_count == 0


@pytest.mark.asyncio
async def test_executor_marks_ingest_failed_on_exception():
    """If NowingIngestService raises, output.ingest_status is 'failed'."""
    execute = build_aggregate_executor()

    listing = VnJobAggregatedListing(
        id="vw:1",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Build data pipelines.",
        job_requirement="Python.",
        confidence_score=0.9,
    )
    aggregate_output = VnJobAggregateOutput(items=[listing])

    with (
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
            new=AsyncMock(return_value=aggregate_output),
        ),
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.NowingIngestService",
            return_value=AsyncMock(ingest=AsyncMock(side_effect=RuntimeError("boom"))),
        ),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), _make_context())

    assert output.ingest_status == "failed"
    assert output.ingest_job_id is None


@pytest.mark.asyncio
async def test_executor_falls_back_to_parent_ingest_job_id():
    """If only parent_ingest_job_id is set, use it for the output."""
    execute = build_aggregate_executor()

    listing = VnJobAggregatedListing(
        id="vw:1",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Build data pipelines.",
        job_requirement="Python.",
        confidence_score=0.9,
    )
    aggregate_output = VnJobAggregateOutput(items=[listing])

    class _FakeIngestResult:
        ingest_job_id = None
        parent_ingest_job_id = "parent-abc"
        ingested_source_ids = ["vw:1"]
        noop_source_ids = []
        status = "ok"

    with (
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
            new=AsyncMock(return_value=aggregate_output),
        ),
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.NowingIngestService",
            return_value=AsyncMock(
                ingest=AsyncMock(return_value=_FakeIngestResult())
            ),
        ),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), _make_context())

    assert output.ingest_job_id == "parent-abc"


@pytest.mark.asyncio
async def test_executor_skips_ingest_with_session_none():
    """If context has no session, ingest is not attempted."""
    execute = build_aggregate_executor()

    listing = VnJobAggregatedListing(
        id="vw:1",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Build data pipelines.",
        job_requirement="Python.",
        confidence_score=0.9,
    )
    aggregate_output = VnJobAggregateOutput(items=[listing])

    from types import SimpleNamespace
    ctx = SimpleNamespace(session=None, workspace_id=42, run_id="run-123")

    with patch(
        "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
        new=AsyncMock(return_value=aggregate_output),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), ctx)

    assert output.ingest_status == "no_session"
    assert output.ingest_job_id is None


@pytest.mark.asyncio
async def test_executor_skips_ingest_with_workspace_id_none():
    """If context has no workspace_id, ingest is not attempted."""
    execute = build_aggregate_executor()

    listing = VnJobAggregatedListing(
        id="vw:1",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Build data pipelines.",
        job_requirement="Python.",
        confidence_score=0.9,
    )
    aggregate_output = VnJobAggregateOutput(items=[listing])

    from types import SimpleNamespace
    ctx = SimpleNamespace(session=AsyncMock(), workspace_id=None, run_id="run-123")

    with patch(
        "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
        new=AsyncMock(return_value=aggregate_output),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), ctx)

    assert output.ingest_status == "no_session"
    assert output.ingest_job_id is None


@pytest.mark.asyncio
async def test_executor_catches_unserializable_listing_exception():
    """A single unserializable listing is skipped and the rest ingested."""
    execute = build_aggregate_executor()

    listing = VnJobAggregatedListing(
        id="vw:1",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Build data pipelines.",
        job_requirement="Python.",
        confidence_score=0.9,
    )
    aggregate_output = VnJobAggregateOutput(items=[listing])

    class _FakeIngestResult:
        ingest_job_id = "job-abc"
        parent_ingest_job_id = None
        ingested_source_ids = ["vw:1"]
        noop_source_ids = []
        status = "ok"

    def _raise_then_succeed(*args, **kwargs):
        if kwargs.get("data") == listing:
            raise ValueError("unserializable")
        return []

    with (
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
            new=AsyncMock(return_value=aggregate_output),
        ),
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.NowingIngestService",
            return_value=AsyncMock(
                ingest=AsyncMock(return_value=_FakeIngestResult())
            ),
        ),
        patch(
            "app.capabilities.vn_jobs.aggregate.executor.to_chunks",
            side_effect=_raise_then_succeed,
        ),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), _make_context())

    assert output.ingest_status == "no_chunks"
    assert output.ingest_job_id is None


@pytest.mark.asyncio
async def test_executor_skips_ingest_without_context():
    """If the context has no session/workspace, ingest is not attempted."""
    execute = build_aggregate_executor()

    listing = VnJobAggregatedListing(
        id="vw:1",
        title="Data Engineer",
        company="FPT",
        location="Hà Nội",
        source="vietnamworks",
        job_description="Build data pipelines.",
        job_requirement="Python.",
        confidence_score=0.9,
    )
    aggregate_output = VnJobAggregateOutput(items=[listing])

    with patch(
        "app.capabilities.vn_jobs.aggregate.executor.aggregate_jobs",
        new=AsyncMock(return_value=aggregate_output),
    ):
        output = await execute(VnJobAggregateInput(keyword="test"), None)

    assert output.ingest_status == "no_session"
    assert output.ingest_job_id is None
