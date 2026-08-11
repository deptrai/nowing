"""Integration tests: scraper/aggregator -> to_chunks -> NowingIngestService."""

from __future__ import annotations

import types

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_batdongsan_scrape_to_chunks_to_ingest(
    db_session, db_workspace, monkeypatch
):
    """A batdongsan.scrape run produces Chunks and ingests them to chainlens-research."""
    import httpx
    import respx

    import app.services.chainlens.ingest as ingest_mod
    from app.capabilities.batdongsan.scrape.executor import build_scrape_executor
    from app.capabilities.batdongsan.scrape.schemas import ScrapeInput
    from app.capabilities.core.types import CapabilityContext
    from app.services.chainlens.ingest import NowingIngestService
    from app.services.scraper_chunks.serializer import to_chunks

    monkeypatch.setattr(
        ingest_mod,
        "config",
        types.SimpleNamespace(
            CHAINLENS_API_URL="https://chainlens.test",
            CHAINLENS_API_KEY="secret",
            CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
            CHAINLENS_INGEST_TIMEOUT_SECONDS=5,
            CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=3,
        ),
    )

    async def fake_scrape(actor_input, **kwargs):
        return {
            "items": [
                {
                    "listing_id": 1,
                    "title": "Bán nhà Ba Đình",
                    "price": "19.8 Tỷ",
                    "area": "75 m²",
                    "district": "Ba Đình",
                    "city": "Hà Nội",
                    "detail_url": "https://bd/1",
                    "phone": "0901234567",
                }
            ],
            "total_items": 1,
            "degraded": False,
        }

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    scrape_output = await execute(ScrapeInput(city="HN", max_items=1), ctx)

    fetched_at = "2026-08-11T00:00:00+00:00"
    chunks = [
        chunk
        for item in scrape_output.items
        for chunk in to_chunks(
            domain="bds",
            data=item,
            fetched_at=fetched_at,
            content_type="listing",
        )
    ]

    assert len(chunks) > 0
    assert all(chunk.metadata.source == "nowing_scraper" for chunk in chunks)
    assert all(chunk.metadata.domain == "bds" for chunk in chunks)

    with respx.mock:
        route = respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(200, json={"ingestJobId": "job-bds-123"})
        )
        service = NowingIngestService()
        result = await service.ingest(
            scraper_id="batdongsan",
            chunks=chunks,
            workspace_id=db_workspace.id,
            session=db_session,
        )

    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer secret"
    assert result.ingest_job_id == "job-bds-123"


@pytest.mark.asyncio
async def test_vn_jobs_aggregate_to_chunks_to_ingest(
    db_session, db_workspace, monkeypatch
):
    """vn_jobs.aggregate output is chunked and sent to chainlens-research."""
    import httpx
    import respx

    import app.services.chainlens.ingest as ingest_mod
    from app.capabilities.core.types import CapabilityContext
    from app.services.chainlens.ingest import NowingIngestService
    from app.services.jobs_aggregator.orchestrator import aggregate_jobs
    from app.services.jobs_aggregator.schemas import VnJobAggregateInput
    from app.services.scraper_chunks.serializer import to_chunks

    monkeypatch.setattr(
        ingest_mod,
        "config",
        types.SimpleNamespace(
            CHAINLENS_API_URL="https://chainlens.test",
            CHAINLENS_API_KEY="secret",
            CHAINLENS_INGEST_MAX_BATCH_SIZE=1000,
            CHAINLENS_INGEST_TIMEOUT_SECONDS=5,
            CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS=3,
        ),
    )

    async def fake_call_source(source: str, payload: dict, ctx):
        if source == "vietnamworks":
            return {
                "items": [
                    {
                        "id": "vw:1",
                        "title": "Senior Data Engineer",
                        "company": "ACB",
                        "location": "Hà Nội",
                        "salary_raw": "Từ 30 triệu",
                        "salary_min": 30000000,
                        "salary_max": 0,
                        "salary_currency": "VND",
                        "salary_period_id": 2,
                        "posted_at": "2026-08-11",
                        "employment_type": "full_time",
                        "source_url": "https://vw.example/1",
                    }
                ],
                "cost_micros": 3500,
                "degraded": False,
            }
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: tos_pending",
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    aggregate_output = await aggregate_jobs(
        VnJobAggregateInput(keyword="data engineer", sources=["vietnamworks", "topcv"]),
        ctx,
    )

    fetched_at = "2026-08-11T00:00:00+00:00"
    chunks = [
        chunk
        for item in aggregate_output.items
        for chunk in to_chunks(
            domain="vn_jobs",
            data=item.model_dump(),
            fetched_at=fetched_at,
            content_type="job_posting",
        )
    ]

    assert len(chunks) > 0
    assert all(chunk.metadata.source == "nowing_scraper" for chunk in chunks)
    assert all(chunk.metadata.domain == "vn_jobs" for chunk in chunks)

    with respx.mock:
        route = respx.post("https://chainlens.test/v1/ingest/scraper").mock(
            return_value=httpx.Response(200, json={"ingestJobId": "job-jobs-456"})
        )
        service = NowingIngestService()
        result = await service.ingest(
            scraper_id="vn_jobs.aggregate",
            chunks=chunks,
            workspace_id=db_workspace.id,
            session=db_session,
        )

    assert route.called
    assert result.ingest_job_id == "job-jobs-456"
