"""Unit tests for ``app.proprietary.platforms.vietnamworks`` fetcher (Story 12.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.proprietary.platforms.vietnamworks.scraper import scrape_vietnamworks

pytestmark = pytest.mark.unit

_FIXTURE = (
    Path(__file__).resolve().parents[5]
    / "tests/unit/capabilities/vietnamworks/fixtures/sample-response-page-1.json"
)


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _build_response(payload: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=payload,
        request=httpx.Request("POST", "https://ms.vietnamworks.com/job-search/v1.0/search"),
    )


class TestScraperApiCall:
    """AC-1: calls VietnamWorks public API."""

    @pytest.mark.asyncio
    async def test_posts_to_ms_vietnamworks_job_search(self, monkeypatch):
        mock_post = AsyncMock(return_value=_build_response(_load_fixture()))

        class _FakeClient:
            async def post(self, url: str, **kwargs: Any) -> httpx.Response:
                await mock_post(url, **kwargs)
                return _build_response(_load_fixture())

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        await scrape_vietnamworks({"keyword": "data engineer", "hitsPerPage": 50, "page": 1})

        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert args[0] == "https://ms.vietnamworks.com/job-search/v1.0/search"
        assert kwargs["json"]["keyword"] == "data engineer"
        assert "Content-Type" in kwargs.get("headers", {})
        assert "User-Agent" in kwargs.get("headers", {})

    @pytest.mark.asyncio
    async def test_sends_no_auth(self, monkeypatch):
        captured: dict[str, Any] = {}

        class _FakeClient:
            async def post(self, url: str, **kwargs: Any) -> httpx.Response:
                captured["headers"] = kwargs.get("headers", {})
                return _build_response(_load_fixture())

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        await scrape_vietnamworks({"keyword": "data engineer"})

        assert "Authorization" not in captured.get("headers", {})

    @pytest.mark.asyncio
    async def test_sends_hits_per_page_and_page(self, monkeypatch):
        captured: dict[str, Any] = {}

        class _FakeClient:
            async def post(self, url: str, **kwargs: Any) -> httpx.Response:
                captured["json"] = kwargs.get("json", {})
                return _build_response(_load_fixture())

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        await scrape_vietnamworks({"keyword": "data engineer", "hitsPerPage": 50, "page": 2})

        assert captured["json"]["hitsPerPage"] == 50
        assert captured["json"]["page"] == 2

    @pytest.mark.asyncio
    async def test_sends_filters_in_request_body(self, monkeypatch):
        captured: dict[str, Any] = {}

        class _FakeClient:
            async def post(self, url: str, **kwargs: Any) -> httpx.Response:
                captured["json"] = kwargs.get("json", {})
                return _build_response({"meta": {"nbHits": 0, "nbPages": 0}, "data": []})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        await scrape_vietnamworks({
            "keyword": "data engineer",
            "locationId": 24,
            "salary_min": 10_000_000,
            "salary_max": 50_000_000,
            "experience_years": 3,
            "employment_type": "full_time",
        })

        assert captured["json"]["keyword"] == "data engineer"
        assert captured["json"]["locationId"] == 24
        assert captured["json"]["salaryMin"] == 10_000_000
        assert captured["json"]["salaryMax"] == 50_000_000
        assert captured["json"]["yearsOfExperience"] == 3
        assert captured["json"]["typeWorkingId"] == 1


class TestScraperFieldMapping:
    """AC-2: maps API fields to normalized JobItem."""

    @pytest.mark.asyncio
    async def test_maps_all_required_fields(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response(_load_fixture())

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data engineer", "hitsPerPage": 50, "page": 1})

        assert out["degraded"] is False
        assert len(out["items"]) == 2
        first = out["items"][0]

        required_fields = {
            "id",
            "title",
            "company",
            "location",
            "source_url",
            "salary_raw",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_period_id",
            "employment_type",
            "experience_years",
            "job_description",
            "job_requirement",
            "job_function",
            "skills",
            "benefits",
            "posted_at",
            "approved_at",
            "expired_at",
            "is_active",
            "source",
        }
        missing = required_fields - set(first.keys())
        assert not missing, f"missing fields: {missing}"

        assert first["id"] == "vw:12345"
        assert first["title"] == "Senior Data Engineer"
        assert first["company"] == "FPT Software"
        assert first["location"] == "Hà Nội"
        assert first["source_url"] == "https://www.vietnamworks.com/senior-data-engineer-12345"
        assert first["salary_raw"] == "Từ 25tr ₫/tháng đến 35tr ₫/tháng"
        assert first["salary_min"] == 25_000_000
        assert first["salary_max"] == 35_000_000
        assert first["salary_currency"] == "VND"
        assert first["salary_period_id"] == 1
        assert first["employment_type"] == "full_time"
        assert first["experience_years"] == 3
        assert first["is_active"] is True

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({
                    "meta": {"nbHits": 1, "nbPages": 1},
                    "data": [
                        {
                            "jobId": 999,
                            "jobTitle": "Minimal Job",
                            "companyName": "ACB",
                            "workingLocations": [],
                            "salaryMin": 0,
                            "salaryMax": 0,
                            "salaryCurrency": "VND",
                            "salaryPeriodId": 1,
                            "prettySalary": "Thương lượng",
                            "isActive": True,
                        }
                    ],
                })

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "minimal"})

        first = out["items"][0]
        assert first["location"] is None
        assert first["job_description"] == ""
        assert first["skills"] == []
        assert first["benefits"] == []

    @pytest.mark.asyncio
    async def test_parses_working_locations(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({
                    "meta": {"nbHits": 1, "nbPages": 1},
                    "data": [
                        {
                            "jobId": 1,
                            "jobTitle": "Test",
                            "companyName": "C",
                            "workingLocations": [
                                {"cityNameVI": "Hà Nội", "cityName": "Ha Noi"},
                                {"cityNameVI": "TP. Hồ Chí Minh", "cityName": "Ho Chi Minh"},
                            ],
                            "salaryMin": 0,
                            "salaryMax": 0,
                            "salaryCurrency": "VND",
                            "salaryPeriodId": 1,
                            "prettySalary": "Thương lượng",
                            "isActive": True,
                        }
                    ],
                })

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "test"})

        assert out["items"][0]["location"] == "Hà Nội"

    @pytest.mark.asyncio
    async def test_parses_salary_min_max_currency_period(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({
                    "meta": {"nbHits": 1, "nbPages": 1},
                    "data": [
                        {
                            "jobId": 2,
                            "jobTitle": "Test",
                            "companyName": "C",
                            "workingLocations": [],
                            "salaryMin": 5000,
                            "salaryMax": 0,
                            "salaryCurrency": "USD",
                            "salaryPeriodId": 1,
                            "prettySalary": "$ 5,000 /tháng",
                            "isActive": True,
                        }
                    ],
                })

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "test"})

        item = out["items"][0]
        assert item["salary_min"] == 5000
        assert item["salary_max"] is None
        assert item["salary_currency"] == "USD"
        assert item["salary_period_id"] == 1


class TestScraperPagination:
    """AC-3: pagination behavior."""

    @pytest.mark.asyncio
    async def test_iterates_multiple_pages(self, monkeypatch):
        class _FakeClient:
            call_count = 0

            async def post(self, _url: str, **kwargs: Any) -> httpx.Response:
                type(self).call_count += 1
                page = kwargs["json"]["page"]
                if page == 1:
                    return _build_response({
                        "meta": {"nbHits": 150, "nbPages": 2},
                        "data": [{"jobId": 1, "jobTitle": "A", "companyName": "C", "workingLocations": [], "salaryMin": 0, "salaryMax": 0, "salaryCurrency": "VND", "salaryPeriodId": 1, "prettySalary": "Thương lượng", "isActive": True} for _ in range(100)],
                    })
                return _build_response({
                    "meta": {"nbHits": 150, "nbPages": 2},
                    "data": [{"jobId": 2, "jobTitle": "B", "companyName": "C", "workingLocations": [], "salaryMin": 0, "salaryMax": 0, "salaryCurrency": "VND", "salaryPeriodId": 1, "prettySalary": "Thương lượng", "isActive": True} for _ in range(50)],
                })

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data", "hitsPerPage": 100, "max_items": 150, "max_pages": 5})

        assert _FakeClient.call_count == 2
        assert out["total_items"] == 150

    @pytest.mark.asyncio
    async def test_stops_at_max_pages(self, monkeypatch):
        class _FakeClient:
            call_count = 0

            async def post(self, _url: str, **kwargs: Any) -> httpx.Response:
                type(self).call_count += 1
                return _build_response({
                    "meta": {"nbHits": 300, "nbPages": 10},
                    "data": [{"jobId": 1, "jobTitle": "A", "companyName": "C", "workingLocations": [], "salaryMin": 0, "salaryMax": 0, "salaryCurrency": "VND", "salaryPeriodId": 1, "prettySalary": "Thương lượng", "isActive": True} for _ in range(100)],
                })

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        await scrape_vietnamworks({"keyword": "data", "hitsPerPage": 100, "max_items": 1000, "max_pages": 2})

        assert _FakeClient.call_count == 2

    @pytest.mark.asyncio
    async def test_stops_when_data_empty(self, monkeypatch):
        class _FakeClient:
            call_count = 0

            async def post(self, _url: str, **kwargs: Any) -> httpx.Response:
                type(self).call_count += 1
                return _build_response({
                    "meta": {"nbHits": 0, "nbPages": 0},
                    "data": [],
                })

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert _FakeClient.call_count == 1
        assert out["items"] == []


class TestScraperFailureModes:
    """Failure handling from grill-me."""

    @pytest.mark.asyncio
    async def test_degrades_on_429(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({"detail": "rate limited"}, status=429)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_degrades_on_5xx(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({"detail": "error"}, status=503)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "api_error"

    @pytest.mark.asyncio
    async def test_degrades_on_403_451(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({"detail": "blocked"}, status=403)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "access_blocked"

    @pytest.mark.asyncio
    async def test_degrades_on_timeout(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                raise httpx.TimeoutException("timed out")

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_degrades_on_invalid_json(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return httpx.Response(
                    200,
                    text="not json",
                    request=httpx.Request("POST", "https://ms.vietnamworks.com/job-search/v1.0/search"),
                )

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "decode_error"

    @pytest.mark.asyncio
    async def test_degrades_on_missing_data_field(self, monkeypatch):
        """Schema drift: upstream removes the 'data' envelope field."""

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({"meta": {"nbHits": 1, "nbPages": 1}})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "schema_drift"

    @pytest.mark.asyncio
    async def test_skips_missing_job_id(self, monkeypatch):
        """Schema drift: a job entry loses its jobId; the rest of the page is kept."""
        fixture = _load_fixture()
        fixture["data"][0].pop("jobId", None)

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response(fixture)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is False
        assert out["total_items"] == 1
        assert out["items"][0]["id"] == "vw:12346"

    @pytest.mark.asyncio
    async def test_degrades_on_data_not_a_list(self, monkeypatch):
        """Schema drift: 'data' becomes an object instead of a list."""

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({"meta": {"nbHits": 1, "nbPages": 1}, "data": {"unexpected": True}})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "schema_drift"


class TestScraperEdgeCases:
    """Boundary and zero-value behaviour for the fetcher."""

    @pytest.mark.asyncio
    async def test_short_circuits_on_max_pages_zero(self, monkeypatch):
        calls: list[Any] = []

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                calls.append(_kwargs)
                return _build_response({"meta": {"nbHits": 1, "nbPages": 1}, "data": []})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data", "max_pages": 0})

        assert out["degraded"] is False
        assert out["items"] == []
        assert out["total_items"] == 0
        assert calls == []

    @pytest.mark.asyncio
    async def test_short_circuits_on_max_items_zero(self, monkeypatch):
        calls: list[Any] = []

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                calls.append(_kwargs)
                return _build_response({"meta": {"nbHits": 1, "nbPages": 1}, "data": []})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data", "max_items": 0})

        assert out["degraded"] is False
        assert out["items"] == []
        assert out["total_items"] == 0
        assert calls == []

    @pytest.mark.asyncio
    async def test_short_circuits_on_hits_per_page_zero(self, monkeypatch):
        calls: list[Any] = []

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                calls.append(_kwargs)
                return _build_response({"meta": {"nbHits": 1, "nbPages": 1}, "data": []})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data", "hitsPerPage": 0})

        assert out["degraded"] is False
        assert out["items"] == []
        assert out["total_items"] == 0
        assert calls == []

    @pytest.mark.asyncio
    async def test_retries_429_then_succeeds(self, monkeypatch):
        attempts: list[int] = []

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                attempts.append(len(attempts) + 1)
                if len(attempts) == 1:
                    return _build_response({"meta": {"nbHits": 1, "nbPages": 1}, "data": []}, status=429)
                return _build_response(_load_fixture())

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        out = await scrape_vietnamworks({"keyword": "data", "max_items": 1})

        assert out["degraded"] is False
        assert out["total_items"] == 1
        assert len(attempts) == 2

    @pytest.mark.asyncio
    async def test_degrades_rate_limited_after_retries_exhausted(self, monkeypatch):
        attempts: list[int] = []

        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                attempts.append(len(attempts) + 1)
                return _build_response({"meta": {"nbHits": 1, "nbPages": 1}, "data": []}, status=429)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        out = await scrape_vietnamworks({"keyword": "data", "max_items": 1})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "rate_limited"
        assert len(attempts) == 3  # default retry attempts + 1

    @pytest.mark.asyncio
    async def test_degrades_on_connect_error(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                raise httpx.ConnectError("connection refused")

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "api_error"

    @pytest.mark.asyncio
    async def test_degrades_on_4xx_other_than_403_451(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response({"error": "bad request"}, status=400)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "api_error"

    @pytest.mark.asyncio
    async def test_degrades_on_non_dict_json_response(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return httpx.Response(
                    status_code=200,
                    json=["unexpected list"],
                    request=httpx.Request("POST", "https://ms.vietnamworks.com/job-search/v1.0/search"),
                )

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "decode_error"


class TestScraperGoldenRegression:
    """Golden fixture regression for the parser."""

    @pytest.mark.asyncio
    async def test_golden_fixture_parses_exactly(self, monkeypatch):
        class _FakeClient:
            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                return _build_response(_load_fixture())

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_vietnamworks({"keyword": "data engineer", "max_items": 2, "max_pages": 1})

        assert out["degraded"] is False
        assert out["total_items"] == 2
        first, second = out["items"]
        assert first["id"] == "vw:12345"
        assert first["title"] == "Senior Data Engineer"
        assert first["salary_min"] == 25_000_000
        assert first["salary_max"] == 35_000_000
        assert first["posted_at"] == "2026-08-04"
        assert second["id"] == "vw:12346"
        assert second["salary_min"] == 0
        assert second["salary_max"] == 0
        assert second["posted_at"] == "2026-08-03"


class TestScraper60sTimeout:
    """AC-108: a 61s HTTP hang must be terminated and reported as timeout."""

    @pytest.mark.asyncio
    async def test_degrades_on_61s_http_hang(self, monkeypatch):
        import asyncio

        import respx

        from app.proprietary.platforms.vietnamworks import scraper as scraper_module

        monkeypatch.setattr(scraper_module, "_REQUEST_TIMEOUT", 0.1)

        async def _hang(request):
            await asyncio.sleep(61)
            return httpx.Response(200, json={"data": []})

        with respx.mock:
            respx.post("https://ms.vietnamworks.com/job-search/v1.0/search").mock(
                side_effect=_hang
            )
            start = asyncio.get_event_loop().time()
            out = await scrape_vietnamworks(
                {"keyword": "data engineer", "max_items": 1, "max_pages": 1}
            )
            elapsed = asyncio.get_event_loop().time() - start

        assert out["degraded"] is True
        assert out["degradation_reason"] == "timeout"
        assert elapsed < 2.0
