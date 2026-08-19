"""Unit tests for ``app.proprietary.platforms.itviec`` scraper (Story 12.3)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.proprietary.platforms.itviec.scraper import scrape_itviec

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _search_html() -> str:
    return _load("search-page.html")


def _detail_html() -> str:
    return _load("detail-page.html")


def _build_response(text: str, status: int = 200, url: str = "https://itviec.com") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        text=text,
        request=httpx.Request("GET", url),
    )


def _fake_client_class() -> type:
    search_html = _search_html()
    detail_html = _detail_html()

    class _FakeClient:
        async def get(self, url: str, **kwargs: Any) -> httpx.Response:
            if "/content" in url:
                return _build_response(detail_html, url=url)
            return _build_response(search_html, url=url)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: Any):
            return None

    return _FakeClient


class TestScraperApiCall:
    """AC-1: fetches ITviec search and detail pages."""

    @pytest.mark.asyncio
    async def test_fetches_search_and_detail_pages(self, monkeypatch):
        real_client = _fake_client_class()()
        mock_get = AsyncMock(side_effect=real_client.get)

        class _FakeClient:
            async def get(self, url: str, **kwargs: Any) -> httpx.Response:
                return await mock_get(url, **kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_itviec({"keyword": "data engineer", "max_items": 1, "max_pages": 1})

        assert out["degraded"] is False
        assert len(out["items"]) == 1
        assert mock_get.called
        call_urls = [call.args[0] for call in mock_get.call_args_list]
        assert any("/it-jobs/data-engineer" in u for u in call_urls)
        assert any("/content" in u for u in call_urls)


class TestScraperFieldMapping:
    """AC-2: maps HTML fields to normalized JobItem."""

    @pytest.mark.asyncio
    async def test_maps_required_fields(self, monkeypatch):
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _fake_client_class()())

        out = await scrape_itviec({"keyword": "data engineer", "max_items": 1, "max_pages": 1})

        assert out["degraded"] is False
        assert out["total_items"] == 1
        item = out["items"][0]
        assert item["id"].startswith("itviec:")
        assert "data-engineer" in item["id"]
        assert item["title"] == "Data Engineer, Global E-commerce Data Platform"
        assert item["company"] == "Crossian"
        assert "Ha Noi" in (item["location"] or "")
        assert "itviec.com" in item["source_url"]
        assert item["salary_raw"] == "Sign in to view salary"
        assert item["salary_min"] == 0
        assert item["salary_max"] == 0
        assert item["salary_currency"] == "VND"
        assert item["salary_period_id"] == "hidden"
        assert item["employment_type"] == "full_time"
        assert item["is_active"] is True
        assert item["source"] == "itviec"

    @pytest.mark.asyncio
    async def test_extracts_job_description_and_requirement(self, monkeypatch):
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _fake_client_class()())

        out = await scrape_itviec({"keyword": "data engineer", "max_items": 1, "max_pages": 1})

        item = out["items"][0]
        assert "ABOUT THE ROLE" in item["job_description"]
        assert "Bachelor" in item["job_requirement"]

    @pytest.mark.asyncio
    async def test_extracts_skills_and_job_domain(self, monkeypatch):
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _fake_client_class()())

        out = await scrape_itviec({"keyword": "data engineer", "max_items": 1, "max_pages": 1})

        item = out["items"][0]
        assert "Data Engineer" in item["skills"]
        assert "AWS" in item["skills"]
        assert item.get("job_domain")


class TestScraperPagination:
    """AC-3: pagination and limits."""

    @pytest.mark.asyncio
    async def test_respects_max_items_and_stops(self, monkeypatch):
        class _FakeClient:
            call_count = 0

            async def get(self, url: str, **kwargs: Any) -> httpx.Response:
                type(self).call_count += 1
                if "/content" in url:
                    return _build_response(_detail_html(), url=url)
                return _build_response(_search_html(), url=url)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_itviec({"keyword": "data engineer", "max_items": 3, "max_pages": 2})

        assert len(out["items"]) == 3
        assert _FakeClient.call_count >= 3  # search + 2 details at minimum


class TestScraperFailureModes:
    """Failure handling from grill-me."""

    @pytest.mark.asyncio
    async def test_degrades_on_429(self, monkeypatch):
        class _FakeClient:
            async def get(self, url: str, **kwargs: Any) -> httpx.Response:
                return _build_response("rate limited", status=429)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_itviec({"keyword": "data engineer"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_degrades_on_403(self, monkeypatch):
        class _FakeClient:
            async def get(self, url: str, **kwargs: Any) -> httpx.Response:
                return _build_response("blocked", status=403)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_itviec({"keyword": "data engineer"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "access_blocked"

    @pytest.mark.asyncio
    async def test_degrades_on_timeout(self, monkeypatch):
        class _FakeClient:
            async def get(self, url: str, **kwargs: Any) -> httpx.Response:
                raise httpx.TimeoutException("timed out")

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: Any):
                return None

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

        out = await scrape_itviec({"keyword": "data engineer"})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_returns_empty_on_zero_max_items(self, monkeypatch):
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _fake_client_class()())

        out = await scrape_itviec({"keyword": "data engineer", "max_items": 0})

        assert out["degraded"] is False
        assert out["items"] == []

    @pytest.mark.asyncio
    async def test_degrades_on_61s_http_hang(self, monkeypatch):
        """A 61s HTTP hang must be terminated and reported as timeout."""
        import asyncio

        import respx

        from app.proprietary.platforms.itviec import scraper as scraper_module

        monkeypatch.setattr(scraper_module, "_REQUEST_TIMEOUT", 0.1)

        async def _hang(request):
            await asyncio.sleep(61)
            return httpx.Response(200, text="")

        with respx.mock:
            respx.get("https://itviec.com/it-jobs/data-engineer").mock(
                side_effect=_hang
            )
            respx.get(
                re.compile(r"https://itviec\.com/it-jobs/data-engineer\?page=\d+")
            ).mock(side_effect=_hang)
            respx.get(
                re.compile(r"https://itviec\.com/.*/content")
            ).mock(side_effect=_hang)

            start = asyncio.get_event_loop().time()
            out = await scrape_itviec(
                {"keyword": "data engineer", "max_items": 1, "max_pages": 1}
            )
            elapsed = asyncio.get_event_loop().time() - start

        assert out["degraded"] is True
        assert out["degradation_reason"] == "timeout"
        assert elapsed < 2.0
