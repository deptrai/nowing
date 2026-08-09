"""Unit tests for ``app.proprietary.platforms.topcv`` scraper (Story 12.2)."""

from __future__ import annotations

import time
import types
from pathlib import Path
from typing import Any

import pytest

from app.config import config
from app.proprietary.platforms.topcv.scraper import (
    _backoff_seconds,
    _fetch_search_page,
    _parse_detail_markdown,
    _parse_search_page,
    _record_failure,
    _validate_search_page,
    scrape_topcv,
)

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _search_html() -> str:
    return _load("search-page.html")


def _detail_markdown() -> str:
    return _load("detail-markdown.txt")


def _detail_metadata() -> dict[str, Any]:
    return {
        "description": (
            "Công ty Công Ty TNHH LG CNS VIỆT NAM tuyển ETL Developer - Data Engineer "
            "tại Cầu Giấy - Hà Nội, lương Thoả thuận, kinh nghiệm 3 năm, "
            "kỹ năng SQL, Phân tích dữ liệu, Python Hoặc Java, "
            "Thiết Kế Cơ Sở Dữ Liệu, Kiến Trúc Etl"
        )
    }


class TestSearchPageParser:
    """AC-2: maps search HTML fields to normalized JobItem."""

    def test_extracts_job_cards(self):
        cards = _parse_search_page(_search_html())
        assert len(cards) == 50

    def test_maps_required_fields(self):
        cards = _parse_search_page(_search_html())
        item = cards[0]
        assert item["id"] == "topcv:1599438"
        assert item["title"] == "ETL Developer - Data Engineer"
        assert item["company"] == "Công Ty TNHH LG CNS VIỆT NAM"
        assert item["location"] == "Hà Nội"
        assert "topcv.vn" in item["source_url"]
        assert item["salary_raw"] == "Thoả thuận"
        assert item["salary_hidden"] is True
        assert item["salary_confidence"] == "low"
        assert item["salary_min"] == 0
        assert item["salary_max"] == 0
        assert item["salary_currency"] == "VND"
        assert item["salary_period_id"] == "negotiable"
        assert item["experience_years"] == 3
        assert item["source"] == "topcv"

    def test_filters_experience_tags(self):
        cards = _parse_search_page(_search_html())
        skills = cards[0]["skills"]
        assert "Data Engineer" in skills
        assert not any("năm" in s for s in skills)
        assert not any("..." in s for s in skills)


class TestDetailParser:
    """AC-2: maps detail markdown to normalized fields."""

    def test_extracts_description_and_requirements(self):
        detail = _parse_detail_markdown(_detail_markdown(), _detail_metadata())
        assert "Develop in web application" in detail["job_description"]
        assert "Bachelor" in detail["job_requirement"]

    def test_extracts_location_and_employment_type(self):
        detail = _parse_detail_markdown(_detail_markdown(), _detail_metadata())
        assert "Hà Nội" in (detail["location"] or "")
        assert detail["employment_type"] == "full_time"

    def test_extracts_skills_and_experience(self):
        detail = _parse_detail_markdown(_detail_markdown(), _detail_metadata())
        assert "SQL" in detail["skills"]
        assert detail["experience_years"] == 3


class TestScraperOrchestration:
    """AC-1: fetches TopCV search + detail pages."""

    @pytest.mark.asyncio
    async def test_returns_items_with_detail(self, monkeypatch):
        detail = _parse_detail_markdown(_detail_markdown(), _detail_metadata())

        async def _fake_search(keyword: str, page: int) -> str:
            return _search_html()

        async def _fake_detail(url: str) -> dict[str, Any]:
            return detail

        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper._fetch_search_page", _fake_search
        )
        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper._fetch_detail_page", _fake_detail
        )

        out = await scrape_topcv({"keyword": "data engineer", "max_items": 1, "max_pages": 1})

        assert out["degraded"] is False
        assert out["total_items"] == 1
        item = out["items"][0]
        assert item["title"] == "ETL Developer - Data Engineer"
        assert "Bachelor" in item["job_requirement"]
        assert "SQL" in item["skills"]

    @pytest.mark.asyncio
    async def test_respects_max_items(self, monkeypatch):
        search_html = _search_html()

        async def _fake_search(keyword: str, page: int) -> str:
            return search_html

        detail = _parse_detail_markdown(_detail_markdown(), _detail_metadata())

        async def _fake_detail(url: str) -> dict[str, Any]:
            return detail

        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper._fetch_search_page", _fake_search
        )
        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper._fetch_detail_page", _fake_detail
        )

        out = await scrape_topcv({"keyword": "data engineer", "max_items": 3, "max_pages": 1})

        assert len(out["items"]) == 3


class TestScraperFailureModes:
    """AC-2/AC-3: handles anti-bot blocks."""

    @pytest.mark.asyncio
    async def test_degrades_on_search_failure(self, monkeypatch):
        async def _fake_search(keyword: str, page: int) -> str:
            raise ValueError("blocked")

        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper._fetch_search_page", _fake_search
        )

        out = await scrape_topcv({"keyword": "data engineer", "max_items": 1, "max_pages": 1})

        assert out["degraded"] is True
        assert out["degradation_reason"] == "bot_detected"

    @pytest.mark.asyncio
    async def test_degrades_after_three_detail_anti_bot(self, monkeypatch):
        search_html = _search_html()

        async def _fake_search(*_):
            return search_html

        call_count = 0

        async def _fake_detail(*_):
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper._fetch_search_page", _fake_search
        )
        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper._fetch_detail_page", _fake_detail
        )

        out = await scrape_topcv(
            {"keyword": "data engineer", "max_items": 10, "max_pages": 1}
        )

        assert out["degraded"] is True
        assert out["degradation_reason"] == "bot_detected"
        assert call_count == 3


class _FakeText:
    def __init__(self, text: str):
        self.text = text


class _FakePage:
    def __init__(self, html_content: str = "", status: int = 200, title: str = ""):
        self.html_content = html_content
        self.status = status
        self._title = title

    def css(self, selector: str) -> list[Any]:
        if selector == "title":
            return [_FakeText(self._title)]
        return []


class TestValidateSearchPage:
    """AC-2: rejects blocked or empty search pages."""

    def test_raises_on_empty_html(self):
        with pytest.raises(ValueError, match="empty search page"):
            _validate_search_page(_FakePage(html_content="", status=200))

    def test_raises_on_403(self):
        with pytest.raises(ValueError, match="anti-bot challenge"):
            _validate_search_page(_FakePage(html_content="blocked", status=403))

    def test_raises_on_429(self):
        with pytest.raises(ValueError, match="rate limited"):
            _validate_search_page(_FakePage(html_content="slow down", status=429))

    def test_raises_on_cloudflare_title(self):
        page = _FakePage(
            html_content="<title>Just a moment...</title>",
            status=200,
            title="Just a moment...",
        )
        with pytest.raises(ValueError, match="anti-bot challenge"):
            _validate_search_page(page)


class TestBackoff:
    """AC-3: backoff grows geometrically and is capped."""

    def test_backoff_increases_and_caps(self, monkeypatch):
        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper.random",
            types.SimpleNamespace(uniform=lambda a, b: 0.0),
        )
        monkeypatch.setattr(config, "TOPCV_RETRY_BACKOFF_BASE_S", 2.0)

        b0 = _backoff_seconds(0)
        b1 = _backoff_seconds(1)
        b2 = _backoff_seconds(2)
        b10 = _backoff_seconds(10)

        assert b0 < b1 < b2
        assert b10 == 30.0


class TestRecordFailure:
    """AC-3: circuit breaker opens after consecutive failures."""

    @pytest.mark.asyncio
    async def test_opens_circuit_after_threshold(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_CIRCUIT_BREAKER_THRESHOLD", 3)
        monkeypatch.setattr(config, "TOPCV_CIRCUIT_BREAKER_TIMEOUT_S", 1.0)

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 0
            scraper._circuit_open_until = 0.0

        try:
            for _ in range(config.TOPCV_CIRCUIT_BREAKER_THRESHOLD - 1):
                await _record_failure()

            async with scraper._circuit_lock:
                assert scraper._circuit_open_until == 0.0
                assert scraper._consecutive_failures == 2

            await _record_failure()

            async with scraper._circuit_lock:
                assert scraper._circuit_open_until > time.monotonic()
        finally:
            async with scraper._circuit_lock:
                scraper._consecutive_failures = 0
                scraper._circuit_open_until = 0.0


class _FakeFetcher:
    def __init__(self, pages: list[Any]):
        self.pages = pages
        self.calls = 0

    def fetch(self, *_, **__) -> Any:
        page = self.pages[min(self.calls, len(self.pages) - 1)]
        self.calls += 1
        if isinstance(page, BaseException):
            raise page
        return page


class TestFetchSearchPage:
    """AC-1/AC-3: retries transient failures and degrades on blocks."""

    @pytest.fixture(autouse=True)
    def _patch_helpers(self, monkeypatch):
        monkeypatch.setattr(
            "app.proprietary.web_crawler.stealth.get_stealth_config", lambda: {}
        )
        monkeypatch.setattr(
            "app.proprietary.web_crawler.stealth.build_stealthy_kwargs", lambda _cfg: {}
        )

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        valid_page = _FakePage(
            html_content="<html><head><title>TopCV</title></head><body>jobs</body></html>",
            status=200,
            title="TopCV",
        )
        fetcher = _FakeFetcher([
            ValueError("transient"),
            ValueError("transient"),
            valid_page,
        ])
        monkeypatch.setattr(scraper, "StealthyFetcher", fetcher)
        monkeypatch.setattr(scraper, "_backoff_seconds", lambda _attempt: 0.0)

        html = await _fetch_search_page("data engineer", 1)

        assert html == valid_page.html_content
        assert fetcher.calls == 3

    @pytest.mark.asyncio
    async def test_degrades_on_rate_limit(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        rate_limited = _FakePage(
            html_content="rate limited",
            status=429,
        )
        fetcher = _FakeFetcher([rate_limited])
        monkeypatch.setattr(scraper, "StealthyFetcher", fetcher)
        monkeypatch.setattr(scraper, "_backoff_seconds", lambda _attempt: 0.0)

        with pytest.raises(ValueError, match="rate_limited"):
            await _fetch_search_page("data engineer", 1)

    @pytest.mark.asyncio
    async def test_raises_when_circuit_open(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_CIRCUIT_BREAKER_TIMEOUT_S", 3600.0)

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 5
            scraper._circuit_open_until = time.monotonic() + 3600.0

        try:
            with pytest.raises(ValueError, match="circuit open"):
                await _fetch_search_page("data engineer", 1)
        finally:
            async with scraper._circuit_lock:
                scraper._consecutive_failures = 0
                scraper._circuit_open_until = 0.0
