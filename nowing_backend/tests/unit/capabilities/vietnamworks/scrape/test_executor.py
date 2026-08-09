"""Unit tests for ``vietnamworks.scrape`` executor (Story 12.1)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.capabilities.vietnamworks.scrape.executor import build_scrape_executor
from app.capabilities.vietnamworks.scrape.schemas import ScrapeInput, ScrapeOutput
from app.config import config

pytestmark = pytest.mark.unit


_PARSED_ITEM = {
    "id": "vw:12345",
    "title": "Senior Data Engineer",
    "company": "FPT Software",
    "location": "Hà Nội",
    "source_url": "https://www.vietnamworks.com/senior-data-engineer-12345",
    "salary_raw": "Từ 25tr ₫/tháng đến 35tr ₫/tháng",
    "salary_min": 25_000_000,
    "salary_max": 35_000_000,
    "salary_currency": "VND",
    "salary_period_id": 1,
    "employment_type": "full_time",
    "experience_years": 3,
    "job_description": "<p>Build data pipelines and warehouses.</p>",
    "job_requirement": "<p>3+ years of Python and SQL.</p>",
    "skills": ["Python", "SQL"],
    "benefits": ["Laptop", "Remote 2 days/week"],
    "posted_at": "2026-08-04",
    "approved_at": "2026-08-04",
    "expired_at": "2026-09-04",
    "is_active": True,
    "source": "vietnamworks",
}


def _make_fake_fetcher(
    *, items: list[dict[str, Any]] | None = None, degraded: bool = False, reason: str | None = None
) -> Callable[..., Awaitable[dict[str, Any]]]:
    items = items or []

    async def fake(_params: dict[str, Any]) -> dict[str, Any]:
        return {
            "items": items,
            "cost_micros": 0,
            "degraded": degraded,
            "degradation_reason": reason,
            "meta": {"nbPages": 1},
        }

    return fake


class TestExecutorMapsUpstreamResponse:
    """AC-1, AC-2: executor maps upstream response to typed ScrapeOutput."""

    @pytest.mark.asyncio
    async def test_returns_typed_job_items_with_all_required_fields(self):
        fake = _make_fake_fetcher(items=[_PARSED_ITEM])
        execute = build_scrape_executor(scrape_fn=fake)

        out = await execute(ScrapeInput(keyword="data engineer", max_items=1))

        assert isinstance(out, ScrapeOutput)
        assert out.total_items == 1
        assert len(out.items) == 1
        assert out.items[0]["id"] == "vw:12345"
        assert out.items[0]["source"] == "vietnamworks"

    @pytest.mark.asyncio
    async def test_normalizes_salary_fields(self):
        fake = _make_fake_fetcher(items=[_PARSED_ITEM])
        execute = build_scrape_executor(scrape_fn=fake)

        out = await execute(ScrapeInput(keyword="data engineer"))

        item = out.items[0]
        assert item["salary_raw"] == "Từ 25tr ₫/tháng đến 35tr ₫/tháng"
        assert item["salary_min"] == 25_000_000
        assert item["salary_max"] == 35_000_000
        assert item["salary_currency"] == "VND"

    @pytest.mark.asyncio
    async def test_maps_type_working_id_to_employment_type(self):
        fake = _make_fake_fetcher(items=[_PARSED_ITEM])
        execute = build_scrape_executor(scrape_fn=fake)

        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.items[0]["employment_type"] == "full_time"

    @pytest.mark.asyncio
    async def test_parses_working_locations_preferring_city_name_vi(self):
        fake = _make_fake_fetcher(items=[_PARSED_ITEM])
        execute = build_scrape_executor(scrape_fn=fake)

        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.items[0]["location"] == "Hà Nội"


class TestExecutorPaginationAndRateLimit:
    """AC-3: pagination and rate-limit handling."""

    @pytest.mark.asyncio
    async def test_iterates_pages_until_max_items_or_end(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            page = params.get("page", 1)
            if page == 1:
                return {"items": [{"id": f"vw:{10 + i}"} for i in range(50)], "degraded": False}
            return {"items": [{"id": f"vw:{60 + i}"} for i in range(50)], "degraded": False}

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer", max_items=75, max_pages=2))

        assert out.total_items == 75
        assert len(calls) == 2
        assert calls[0]["page"] == 1
        assert calls[1]["page"] == 2
        assert calls[0]["max_pages"] == 1

    @pytest.mark.asyncio
    async def test_sets_hits_per_page_to_min_100_max_items(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            return {"items": [], "degraded": False}

        execute = build_scrape_executor(scrape_fn=fake)
        await execute(ScrapeInput(keyword="data engineer", max_items=30, max_pages=1))

        assert calls[0]["hitsPerPage"] == 30

    @pytest.mark.asyncio
    async def test_stops_when_meta_nb_pages_exceeded(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            page = params.get("page", 1)
            return {
                "items": [{"id": f"vw:{page}"}],
                "meta": {"nbHits": 3, "nbPages": 3},
                "degraded": False,
            }

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer", max_items=100, max_pages=10))

        assert out.total_items == 3
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_stops_after_empty_page(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            if params.get("page", 1) == 1:
                return {"items": [{"id": "vw:1"}], "degraded": False}
            return {"items": [], "degraded": False}

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer", max_items=100, max_pages=5))

        assert out.total_items == 1
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_stops_after_max_items_reached(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            return {"items": [{"id": f"vw:{params.get('page', 1)}"}], "degraded": False}

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer", max_items=1, max_pages=5))

        assert out.total_items == 1
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_omits_none_fields_from_scraper_params(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            assert "salary_min" not in params
            assert "salary_max" not in params
            assert "location" not in params
            return {"items": [{"id": "vw:1"}], "meta": {"nbPages": 1}, "degraded": False}

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.total_items == 1

    @pytest.mark.asyncio
    async def test_respects_max_pages(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            return {"items": [{"id": f"vw:{params.get('page', 1)}"}], "degraded": False}

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer", max_items=100, max_pages=3))

        assert out.total_items == 3
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_stops_when_overfetched_items_exceed_max_items(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            return {"items": [{"id": f"vw:{i}"} for i in range(5)], "degraded": False}

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer", max_items=2, max_pages=3))

        assert out.total_items == 2
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_stops_when_nb_pages_shrinks(self):
        calls: list[dict[str, Any]] = []

        async def fake(params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            page = params.get("page", 1)
            nb_pages = {1: 3, 2: 1}.get(page, 1)
            return {
                "items": [{"id": f"vw:{page}"}],
                "meta": {"nbHits": 10, "nbPages": nb_pages},
                "degraded": False,
            }

        execute = build_scrape_executor(scrape_fn=fake)
        out = await execute(ScrapeInput(keyword="data engineer", max_items=100, max_pages=5))

        assert out.total_items == 2
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_degrades_on_429_with_rate_limited_reason(self):
        class _FakeFetcher:
            async def __call__(self, _params: dict[str, Any]) -> dict[str, Any]:
                return {
                    "items": [],
                    "degraded": True,
                    "degradation_reason": "rate_limited",
                }

        execute = build_scrape_executor(scrape_fn=_FakeFetcher())
        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.degraded is True
        assert out.degradation_reason == "rate_limited"
        assert out.next_action is not None
        assert out.cost_micros == 0

    @pytest.mark.asyncio
    async def test_degrades_on_timeout_with_timeout_reason(self):
        import httpx

        class _FakeFetcher:
            async def __call__(self, _params: dict[str, Any]) -> dict[str, Any]:
                raise httpx.TimeoutException("timed out")

        execute = build_scrape_executor(scrape_fn=_FakeFetcher())
        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.degraded is True
        assert out.degradation_reason == "timeout"
        assert out.cost_micros == 0

    @pytest.mark.asyncio
    async def test_degrades_on_other_runtime_error_with_api_error_reason(self):
        class _FakeFetcher:
            async def __call__(self, _params: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("some random failure")

        execute = build_scrape_executor(scrape_fn=_FakeFetcher())
        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.degraded is True
        assert out.degradation_reason == "api_error"
        assert out.cost_micros == 0


class TestExecutorCostAndBilling:
    """AC-4: cost_micros and billable_units."""

    @pytest.mark.asyncio
    async def test_cost_micros_equals_items_times_rate(self, monkeypatch):
        monkeypatch.setattr(config, "VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM", 3000)
        fake = _make_fake_fetcher(items=[_PARSED_ITEM, {**_PARSED_ITEM, "id": "vw:2"}])
        execute = build_scrape_executor(scrape_fn=fake)

        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.cost_micros == 2 * 3000

    @pytest.mark.asyncio
    async def test_degraded_run_costs_zero(self, monkeypatch):
        monkeypatch.setattr(config, "VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM", 3000)
        fake = _make_fake_fetcher(items=[], degraded=True, reason="rate_limited")
        execute = build_scrape_executor(scrape_fn=fake)

        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.degraded is True
        assert out.cost_micros == 0

    @pytest.mark.asyncio
    async def test_empty_items_cost_zero(self, monkeypatch):
        monkeypatch.setattr(config, "VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM", 3000)
        fake = _make_fake_fetcher(items=[])
        execute = build_scrape_executor(scrape_fn=fake)

        out = await execute(ScrapeInput(keyword="data engineer"))

        assert out.degraded is False
        assert out.cost_micros == 0
