"""Unit tests for ``app.proprietary.platforms.topcv`` scraper (Story 12.2)."""

from __future__ import annotations

import time
import types
from pathlib import Path
from typing import Any

import pytest

from app.config import config
from app.proprietary.platforms.topcv.scraper import (
    _abs_url,
    _backoff_seconds,
    _clean_url,
    _extract_salary_numbers,
    _fetch_detail_page,
    _fetch_search_page,
    _is_requirement_tag,
    _map_employment_type,
    _normalize_keyword,
    _parse_detail_markdown,
    _parse_experience,
    _parse_posted,
    _parse_search_page,
    _record_failure,
    _safe_text,
    _topcv_search_url,
    _user_agent_for_attempt,
    _validate_search_page,
    scrape_topcv,
)
from app.utils.crawl import BlockType

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


def _make_fake_connector(outcomes: list[Any]) -> type:
    class _FakeConnector:
        last: Any = None

        def __init__(self) -> None:
            self.outcomes = outcomes
            self.calls = 0
            _FakeConnector.last = self

        async def crawl_url(self, url: str) -> Any:
            if self.calls >= len(self.outcomes):
                raise ValueError("exhausted")
            outcome = self.outcomes[self.calls]
            self.calls += 1
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

    return _FakeConnector


class _RecordingFetcher:
    def __init__(self, page: _FakePage):
        self.page = page
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def fetch(self, url: str, **kwargs: Any) -> _FakePage:
        self.calls.append((url, kwargs))
        return self.page


def _single_card_with_remaining() -> str:
    return (
        '<html><body>'
        '<div class="job-item-search-result" data-job-id="12345">'
        '<h3 class="title">'
        '<a href="/viec-lam/test-job">'
        '<span data-toggle="tooltip">Python Developer</span>'
        '</a></h3>'
        '<a class="company"><span class="company-name">ACME</span></a>'
        '<label class="address"><span class="city-text">Hà Nội</span></label>'
        '<label class="salary"><span>Thoả thuận</span></label>'
        '<label class="exp"><span>2 năm</span></label>'
        '<label class="label-update">2 ngày trước</label>'
        '<div class="tag">'
        '<a class="item-tag">Python</a>'
        '<span class="remaining-items" data-original-title="'
        'SQL, Docker, Agile">+3</span>'
        '</div></div></body></html>'
    )


def _many_cards(count: int) -> list[dict[str, Any]]:
    return [
        {
            "source_url": f"https://www.topcv.vn/job/{i}",
            "salary_raw": "Thoả thuận",
        }
        for i in range(count)
    ]


class TestSearchPageTags:
    def test_remaining_items_tooltip_adds_skills(self):
        cards = _parse_search_page(_single_card_with_remaining())
        assert len(cards) == 1
        assert cards[0]["skills"] == ["Python", "SQL", "Docker", "Agile"]


class TestUserAgent:
    def test_rotates_user_agent_per_attempt(self, monkeypatch):
        custom = "Custom-Agent/1.0"
        monkeypatch.setattr(config, "TOPCV_USER_AGENT", custom)
        assert _user_agent_for_attempt(1) == custom
        default = _user_agent_for_attempt(2)
        assert default != custom
        assert "Mozilla" in default
        assert _user_agent_for_attempt(3) == custom


class TestValidateSearchPageErrors:
    def test_raises_on_400(self):
        with pytest.raises(ValueError, match="search page error"):
            _validate_search_page(
                _FakePage(html_content="error", status=400)
            )

    def test_raises_on_500(self):
        with pytest.raises(ValueError, match="search page error"):
            _validate_search_page(
                _FakePage(html_content="error", status=500)
            )


class TestFetchSearchPageTimeout:
    @pytest.mark.asyncio
    async def test_passes_timeout_kwarg(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(
            "app.proprietary.web_crawler.stealth.get_stealth_config",
            lambda: {},
        )
        monkeypatch.setattr(
            "app.proprietary.web_crawler.stealth.build_stealthy_kwargs",
            lambda _cfg: {},
        )
        monkeypatch.setattr(config, "TOPCV_TIMEOUT_S", 12.34)

        valid_page = _FakePage(
            html_content="jobs", status=200, title="TopCV"
        )
        fetcher = _RecordingFetcher(valid_page)
        monkeypatch.setattr(scraper, "StealthyFetcher", fetcher)

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 0
            scraper._circuit_open_until = 0.0

        html = await _fetch_search_page("data engineer", 1)
        assert html == valid_page.html_content
        assert fetcher.calls
        assert fetcher.calls[0][1]["timeout"] == 12340


class TestCircuitReset:
    @pytest.mark.asyncio
    async def test_search_success_resets_failures(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(
            "app.proprietary.web_crawler.stealth.get_stealth_config",
            lambda: {},
        )
        monkeypatch.setattr(
            "app.proprietary.web_crawler.stealth.build_stealthy_kwargs",
            lambda _cfg: {},
        )

        valid_page = _FakePage(
            html_content="jobs", status=200, title="TopCV"
        )
        fetcher = _FakeFetcher([valid_page])
        monkeypatch.setattr(scraper, "StealthyFetcher", fetcher)

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 5
            scraper._circuit_open_until = 0.0

        try:
            html = await _fetch_search_page("data engineer", 1)
            assert html == valid_page.html_content

            async with scraper._circuit_lock:
                assert scraper._consecutive_failures == 0

            for _ in range(config.TOPCV_CIRCUIT_BREAKER_THRESHOLD):
                await _record_failure()

            async with scraper._circuit_lock:
                assert scraper._consecutive_failures == 3
                assert scraper._circuit_open_until > time.monotonic()
        finally:
            async with scraper._circuit_lock:
                scraper._consecutive_failures = 0
                scraper._circuit_open_until = 0.0


class TestFetchDetailPageRetry:
    @pytest.mark.asyncio
    async def test_negative_retry_attempts_clamped(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_RETRY_ATTEMPTS", -1)
        monkeypatch.setattr(scraper, "_backoff_seconds", lambda _a: 0.0)

        detail_md = _detail_markdown()
        detail_meta = _detail_metadata()
        expected = _parse_detail_markdown(detail_md, detail_meta)

        success = types.SimpleNamespace(
            status="success".upper().lower(),
            result={"content": detail_md, "metadata": detail_meta},
            block_type=BlockType.OK,
        )
        fake_connector = _make_fake_connector([success])
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            fake_connector,
        )

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 0
            scraper._circuit_open_until = 0.0

        try:
            detail = await _fetch_detail_page("https://topcv.vn/job")
            assert detail == expected
            assert fake_connector.last.calls == 1
        finally:
            async with scraper._circuit_lock:
                scraper._consecutive_failures = 0
                scraper._circuit_open_until = 0.0

    @pytest.mark.asyncio
    async def test_success_detail_returns_and_resets(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_RETRY_ATTEMPTS", 0)
        monkeypatch.setattr(scraper, "_backoff_seconds", lambda _a: 0.0)

        detail_md = _detail_markdown()
        detail_meta = _detail_metadata()
        expected = _parse_detail_markdown(detail_md, detail_meta)

        success = types.SimpleNamespace(
            status="success".upper().lower(),
            result={"content": detail_md, "metadata": detail_meta},
            block_type=BlockType.OK,
        )
        fake_connector = _make_fake_connector([success])
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            fake_connector,
        )

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 5
            scraper._circuit_open_until = 0.0

        try:
            detail = await _fetch_detail_page("https://topcv.vn/job")
            assert detail == expected
            assert fake_connector.last.calls == 1
            async with scraper._circuit_lock:
                assert scraper._consecutive_failures == 0
        finally:
            async with scraper._circuit_lock:
                scraper._consecutive_failures = 0
                scraper._circuit_open_until = 0.0

    @pytest.mark.asyncio
    async def test_retries_after_exception_then_succeeds(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_RETRY_ATTEMPTS", 1)
        monkeypatch.setattr(scraper, "_backoff_seconds", lambda _a: 0.0)

        detail_md = _detail_markdown()
        detail_meta = _detail_metadata()
        expected = _parse_detail_markdown(detail_md, detail_meta)

        success = types.SimpleNamespace(
            status="success".upper().lower(),
            result={"content": detail_md, "metadata": detail_meta},
            block_type=BlockType.OK,
        )
        fake_connector = _make_fake_connector([
            ValueError("transient"),
            success,
        ])
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            fake_connector,
        )

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 5
            scraper._circuit_open_until = 0.0

        try:
            detail = await _fetch_detail_page("https://topcv.vn/job")
            assert detail == expected
            assert fake_connector.last.calls == 2
            async with scraper._circuit_lock:
                assert scraper._consecutive_failures == 0
        finally:
            async with scraper._circuit_lock:
                scraper._consecutive_failures = 0
                scraper._circuit_open_until = 0.0

    @pytest.mark.asyncio
    async def test_retries_after_non_success_then_succeeds(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_RETRY_ATTEMPTS", 1)
        monkeypatch.setattr(scraper, "_backoff_seconds", lambda _a: 0.0)

        detail_md = _detail_markdown()
        detail_meta = _detail_metadata()
        expected = _parse_detail_markdown(detail_md, detail_meta)

        non_success = types.SimpleNamespace(
            status="empty".upper().lower(),
            result={},
            block_type=BlockType.OK,
        )
        success = types.SimpleNamespace(
            status="success".upper().lower(),
            result={"content": detail_md, "metadata": detail_meta},
            block_type=BlockType.OK,
        )
        fake_connector = _make_fake_connector([non_success, success])
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            fake_connector,
        )

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 0
            scraper._circuit_open_until = 0.0

        try:
            detail = await _fetch_detail_page("https://topcv.vn/job")
            assert detail == expected
            assert fake_connector.last.calls == 2
        finally:
            async with scraper._circuit_lock:
                scraper._consecutive_failures = 0
                scraper._circuit_open_until = 0.0


class TestScrapeDefaults:
    @pytest.mark.asyncio
    async def test_empty_params_use_defaults(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_PAGE_DELAY_S", 0.0)
        monkeypatch.setattr(
            config, "TOPCV_SCRAPE_MICROS_PER_ITEM", 1000
        )

        search_calls = []

        async def _fake_search(keyword, page):
            search_calls.append((keyword, page))
            return "<html/>"

        async def _fake_detail(_url):
            return {}

        monkeypatch.setattr(scraper, "_fetch_search_page", _fake_search)
        monkeypatch.setattr(scraper, "_fetch_detail_page", _fake_detail)
        monkeypatch.setattr(
            scraper,
            "_parse_search_page",
            lambda _html: _many_cards(51),
        )

        out = await scrape_topcv({})
        assert search_calls == [("viec-lam", 1)]
        assert out["total_items"] == 50
        assert out["cost_micros"] == 3000
        assert out["degraded"] is False

    @pytest.mark.asyncio
    async def test_zero_max_items_returns_empty(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        calls = []

        async def _fake_search(*args):
            calls.append(args)
            return "<html/>"

        monkeypatch.setattr(scraper, "_fetch_search_page", _fake_search)
        out = await scrape_topcv(
            {"keyword": "data engineer", "max_items": 0, "max_pages": 1}
        )
        assert not calls
        assert out == {
            "items": [],
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 0,
        }

    @pytest.mark.asyncio
    async def test_zero_max_pages_returns_empty(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        calls = []

        async def _fake_search(*args):
            calls.append(args)
            return "<html/>"

        monkeypatch.setattr(scraper, "_fetch_search_page", _fake_search)
        out = await scrape_topcv(
            {"keyword": "data engineer", "max_items": 1, "max_pages": 0}
        )
        assert not calls
        assert out == {
            "items": [],
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 0,
        }

    @pytest.mark.asyncio
    async def test_page_zero_and_negative_clamp_to_one(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        search_calls = []

        async def _fake_search(keyword, page):
            search_calls.append(page)
            return "<html/>"

        monkeypatch.setattr(scraper, "_fetch_search_page", _fake_search)
        monkeypatch.setattr(
            scraper, "_parse_search_page", lambda _html: []
        )
        monkeypatch.setattr(config, "TOPCV_PAGE_DELAY_S", 0.0)

        for page_param in (0, -1):
            search_calls.clear()
            out = await scrape_topcv(
                {
                    "keyword": "data engineer",
                    "page": page_param,
                    "max_items": 1,
                    "max_pages": 1,
                }
            )
            assert search_calls == [1]
            assert out["total_items"] == 0
            assert out["degraded"] is False


class TestScrapePagination:
    @pytest.mark.parametrize(
        "page,max_pages,expected_pages,expected_items",
        [
            (1, 1, [1], 2),
            (1, 2, [1, 2], 4),
            (2, 3, [2, 3, 4], 6),
        ],
    )
    @pytest.mark.asyncio
    async def test_iterates_expected_pages(
        self,
        monkeypatch,
        page,
        max_pages,
        expected_pages,
        expected_items,
    ):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_PAGE_DELAY_S", 0.0)
        monkeypatch.setattr(
            config, "TOPCV_SCRAPE_MICROS_PER_ITEM", 1000
        )
        monkeypatch.setattr(config, "TOPCV_MAX_PAGES", 10)

        search_calls = []

        async def _fake_search(keyword, p):
            search_calls.append((keyword, p))
            return "<html/>"

        async def _fake_detail(_url):
            return {"skills": ["Python"], "salary_raw": ""}

        def _fake_parse(_html):
            return [
                {
                    "source_url": f"https://www.topcv.vn/job/{i}",
                    "salary_raw": "Thoả thuận",
                }
                for i in range(2)
            ]

        monkeypatch.setattr(scraper, "_fetch_search_page", _fake_search)
        monkeypatch.setattr(scraper, "_fetch_detail_page", _fake_detail)
        monkeypatch.setattr(scraper, "_parse_search_page", _fake_parse)

        out = await scrape_topcv(
            {
                "keyword": "data engineer",
                "page": page,
                "max_pages": max_pages,
                "max_items": 10,
            }
        )
        assert search_calls == [
            ("data engineer", p) for p in expected_pages
        ]
        assert out["total_items"] == expected_items
        assert out["degraded"] is False
        expected_cost = (3 * len(expected_pages) + expected_items) * 1000
        assert out["cost_micros"] == expected_cost


# ---------------------------------------------------------------------------
# Helper-function unit tests (targeted at surviving mutants).
# ---------------------------------------------------------------------------


def _el(html: str):
    """Parse an HTML fragment into an lxml element for _safe_text tests."""
    from lxml import html as lxml_html

    return lxml_html.fromstring(html)


class TestSafeText:
    def test_none_returns_none(self):
        assert _safe_text(None) is None

    def test_empty_text_returns_none(self):
        assert _safe_text(_el("<span>   </span>")) is None

    def test_nested_itertext_joined_and_stripped(self):
        assert _safe_text(_el("<div>Hello<b>world</b></div>")) == "Hello world"

    def test_nested_strips_edges_only(self):
        # _safe_text joins itertext with spaces and strips edges only.
        assert _safe_text(_el("<p>\nHello<b>world</b>\n</p>")) == "Hello world"


class TestNormalizeKeyword:
    @pytest.mark.parametrize("value,expected", [
        ("Lập trình viên", "lp-trnh-vin"),
        ("data engineer", "data-engineer"),
        ("c++", "c++"),
        ("c#", "c"),
        ("!!!", "viec-lam"),
        ("a/b", "ab"),
        ("a   b", "a-b"),
        ("-a-", "a"),
    ])
    def test_normalize(self, value, expected):
        assert _normalize_keyword(value) == expected


class TestCleanUrl:
    @pytest.mark.parametrize("url,expected", [
        ("", ""),
        ("/viec-lam/test", "https://www.topcv.vn/viec-lam/test"),
        ("//www.topcv.vn/job/1", "https://www.topcv.vn/job/1"),
        ("https://www.topcv.vn/job/1", "https://www.topcv.vn/job/1"),
        ("https://www.topcv.vn/job/1?page=2", "https://www.topcv.vn/job/1?page=2"),
        ("https://example.com/path?q=1", "https://example.com/path?q=1"),
        ("/job/1?page=2", "https://www.topcv.vn/job/1?page=2"),
    ])
    def test_clean(self, url, expected):
        assert _clean_url(url) == expected


class TestAbsUrl:
    @pytest.mark.parametrize("path,expected", [
        ("", ""),
        ("https://x.com/y", "https://x.com/y"),
        ("/job/1", "https://www.topcv.vn/job/1"),
    ])
    def test_abs(self, path, expected):
        assert _abs_url(path) == expected


class TestTopcvSearchUrl:
    def test_page_one_has_no_query(self):
        url = _topcv_search_url("data engineer", 1)
        assert url == "https://www.topcv.vn/tim-viec-lam-data-engineer"
        assert "?page=" not in url

    def test_page_two_has_query(self):
        assert _topcv_search_url("data engineer", 2).endswith("?page=2")

    def test_page_zero_treated_as_one(self):
        assert "?page=" not in _topcv_search_url("data engineer", 0)


class TestExtractSalaryNumbers:
    @pytest.mark.parametrize("text,expected", [
        ("", (0, 0, "VND", "month", True, "low")),
        (None, (0, 0, "VND", "month", True, "low")),
        ("Thoả thuận", (0, 0, "VND", "negotiable", True, "low")),
        ("Thương lượng", (0, 0, "VND", "negotiable", True, "low")),
        ("15-20 triệu", (15_000_000, 20_000_000, "VND", "month", False, "medium")),
        ("10-20 tr", (10_000_000, 20_000_000, "VND", "month", False, "medium")),
        ("100k", (100_000, None, "VND", "month", False, "medium")),
        ("1b", (1_000_000_000, None, "VND", "month", False, "medium")),
        ("1t", (1_000_000_000_000, None, "VND", "month", False, "medium")),
        ("20m", (20_000_000, None, "VND", "month", False, "medium")),
        ("từ 10 triệu tới 20 triệu", (10_000_000, 20_000_000, "VND", "month", False, "medium")),
        ("từ 10 triệu đến 20 triệu", (10_000_000, 20_000_000, "VND", "month", False, "medium")),
        ("tới 20 triệu", (0, 20_000_000, "VND", "month", False, "medium")),
        ("từ 10 triệu", (10_000_000, None, "VND", "month", False, "medium")),
        ("từ 10 20 triệu", (10_000_000, 20_000_000, "VND", "month", False, "medium")),
        ("up to 5000 usd", (0, 5000, "USD", "month", False, "medium")),
        ("100", (100, None, "VND", "month", False, "medium")),
        ("15 20tr", (15_000_000, 20_000_000, "VND", "month", False, "medium")),
    ])
    def test_exact(self, text, expected):
        assert _extract_salary_numbers(text) == expected

    def test_usd_dollar_sign_only(self):
        # "$" present, "usd" absent -> still USD (kills or->and).
        out = _extract_salary_numbers("$5,000")
        assert out[2] == "USD"
        assert out[0] == 5000
        assert out[1] is None
        assert out[4] is False

    def test_usd_word_only(self):
        out = _extract_salary_numbers("5000 usd")
        assert out[2] == "USD"
        assert out[0] == 5000

    def test_dot_thousands_vnd(self):
        assert _extract_salary_numbers("10.000.000")[0] == 10_000_000

    @pytest.mark.parametrize("text,period", [
        ("100 triệu/năm", "year"),
        ("50k/giờ", "hour"),
        ("200k/ngày", "day"),
        ("10 triệu/tháng", "month"),
        ("5000 usd/year", "year"),
    ])
    def test_period_tag(self, text, period):
        assert _extract_salary_numbers(text)[3] == period

    def test_period_year_value(self):
        assert _extract_salary_numbers("100 triệu/năm")[0] == 100_000_000

    def test_no_numbers_returns_hidden(self):
        out = _extract_salary_numbers("lương cạnh tranh")
        assert out[4] is True
        assert out[5] == "low"

    def test_confidence_medium_when_numbers(self):
        out = _extract_salary_numbers("10 triệu")
        assert out[5] == "medium"
        assert out[4] is False


class TestParsePosted:
    @staticmethod
    def _within_days(iso: str, days: float, tol: float = 60.0) -> bool:
        from datetime import UTC, datetime, timedelta

        got = datetime.fromisoformat(iso)
        expected = datetime.now(UTC) - timedelta(days=days)
        return abs((got - expected).total_seconds()) <= tol

    @pytest.mark.parametrize("text", [None, "", "hôm qua"])
    def test_no_match_returns_none(self, text):
        assert _parse_posted(text) is None

    def test_phut(self):
        from datetime import UTC, datetime, timedelta

        iso = _parse_posted("5 phút trước")
        got = datetime.fromisoformat(iso)
        expected = datetime.now(UTC) - timedelta(minutes=5)
        assert abs((got - expected).total_seconds()) <= 60

    def test_gio(self):
        from datetime import UTC, datetime, timedelta

        iso = _parse_posted("3 giờ trước")
        got = datetime.fromisoformat(iso)
        expected = datetime.now(UTC) - timedelta(hours=3)
        assert abs((got - expected).total_seconds()) <= 60

    @pytest.mark.parametrize("text,days", [
        ("2 ngày trước", 2),
        ("1 tuần trước", 7),
        ("1 tháng trước", 30),
        ("3 tháng trước", 90),
        ("1 năm trước", 365),
        ("2 năm trước", 730),
        ("đăng 4 ngày trước", 4),
        ("  2   ngày   trước  ", 2),
    ])
    def test_delta_within_tolerance(self, text, days):
        # Tolerance of 60s kills NumberReplacer on 30/365 (off by a full day)
        # and Mul_Add/Sub/FloorDiv on `amount * 365`.
        assert self._within_days(_parse_posted(text), days, tol=60)


class TestParseExperience:
    @pytest.mark.parametrize("text,expected", [
        (None, None),
        ("", None),
        ("không yêu cầu", None),
        ("3 năm", 3),
        ("3+ years", 3),
        ("5-10 năm", 10),
        ("2 years", 2),
        ("1 year", 1),
    ])
    def test_parse(self, text, expected):
        assert _parse_experience(text) == expected


class TestIsRequirementTag:
    @pytest.mark.parametrize("text,expected", [
        ("", True),
        (None, True),
        ("3 năm", True),
        ("2 years", True),
        ("kinh nghiệm", True),
        ("trở lên", True),
        ("cao đẳng", True),
        ("đại học", True),
        ("trung cấp", True),
        ("...", True),
        ("Python", False),
        ("Docker", False),
    ])
    def test_is_requirement(self, text, expected):
        assert _is_requirement_tag(text) is expected


class TestMapEmploymentType:
    @pytest.mark.parametrize("text,expected", [
        (None, None),
        ("", None),
        ("something", None),
        ("Toàn thời gian", "full_time"),
        ("Full time", "full_time"),
        ("Full-time", "full_time"),
        ("Bán thời gian", "part_time"),
        ("Part time", "part_time"),
        ("Part-time", "part_time"),
        ("Thực tập", "intern"),
        ("Internship", "intern"),
        ("Hợp đồng", "contract"),
        ("Contract", "contract"),
    ])
    def test_map(self, text, expected):
        assert _map_employment_type(text) == expected


class TestBackoffUniformArgs:
    def test_uniform_called_with_zero_lower_bound(self, monkeypatch):
        # kills NumberReplacer on the `0` arg of random.uniform(0, 0.5).
        captured: list[tuple[float, float]] = []

        def _fake_uniform(a: float, b: float) -> float:
            captured.append((a, b))
            return 0.0

        monkeypatch.setattr(
            "app.proprietary.platforms.topcv.scraper.random",
            types.SimpleNamespace(uniform=_fake_uniform),
        )
        monkeypatch.setattr(config, "TOPCV_RETRY_BACKOFF_BASE_S", 2.0)
        _backoff_seconds(0)
        assert captured[0] == (0, 0.5)


def _reset_circuit(scraper):
    async def _reset():
        async with scraper._circuit_lock:
            scraper._consecutive_failures = 0
            scraper._circuit_open_until = 0.0
    return _reset


class TestFetchDetailPageBlocks:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_RETRY_ATTEMPTS", 0)
        monkeypatch.setattr(scraper, "_backoff_seconds", lambda _a: 0.0)

    @pytest.mark.asyncio
    async def test_rate_limited_outcome_raises(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        rate = types.SimpleNamespace(status="failed", result={}, block_type=BlockType.RATE_LIMITED)
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            _make_fake_connector([rate]),
        )
        await _reset_circuit(scraper)()
        try:
            with pytest.raises(ValueError, match="rate_limited"):
                await _fetch_detail_page("https://topcv.vn/job")
        finally:
            await _reset_circuit(scraper)()

    @pytest.mark.asyncio
    async def test_anti_bot_block_returns_none(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        blocked = types.SimpleNamespace(status="failed", result={}, block_type=BlockType.CLOUDFLARE)
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            _make_fake_connector([blocked]),
        )
        await _reset_circuit(scraper)()
        try:
            assert await _fetch_detail_page("https://topcv.vn/job") is None
        finally:
            await _reset_circuit(scraper)()

    @pytest.mark.asyncio
    async def test_generic_failure_returns_empty_after_retries(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        empty = types.SimpleNamespace(status="failed", result={}, block_type=BlockType.OK)
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            _make_fake_connector([empty]),
        )
        await _reset_circuit(scraper)()
        try:
            assert await _fetch_detail_page("https://topcv.vn/job") == {}
        finally:
            await _reset_circuit(scraper)()

    @pytest.mark.asyncio
    async def test_anti_bot_exception_message_returns_none(self, monkeypatch):
        # kills AddNot on `"anti-bot challenge" in str(exc).lower()`.
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            _make_fake_connector([ValueError("anti-bot challenge")]),
        )
        await _reset_circuit(scraper)()
        try:
            assert await _fetch_detail_page("https://topcv.vn/job") is None
        finally:
            await _reset_circuit(scraper)()

    @pytest.mark.asyncio
    async def test_non_success_with_result_does_not_parse(self, monkeypatch):
        # kills AndWithOr on line 620: status != success but result truthy
        # must NOT enter the success-parsing branch.
        import app.proprietary.platforms.topcv.scraper as scraper

        non_success = types.SimpleNamespace(
            status="failed",
            result={"content": _detail_markdown(), "metadata": _detail_metadata()},
            block_type=BlockType.OK,
        )
        monkeypatch.setattr(
            "app.proprietary.web_crawler.connector.WebCrawlerConnector",
            _make_fake_connector([non_success]),
        )
        await _reset_circuit(scraper)()
        try:
            assert await _fetch_detail_page("https://topcv.vn/job") == {}
        finally:
            await _reset_circuit(scraper)()

    @pytest.mark.asyncio
    async def test_circuit_open_raises_rate_limited(self, monkeypatch):
        import app.proprietary.platforms.topcv.scraper as scraper

        async with scraper._circuit_lock:
            scraper._consecutive_failures = 5
            scraper._circuit_open_until = time.monotonic() + 3600.0
        try:
            with pytest.raises(ValueError, match="rate_limited"):
                await _fetch_detail_page("https://topcv.vn/job")
        finally:
            await _reset_circuit(scraper)()


class TestScrapeEdges:
    @pytest.mark.asyncio
    async def test_stops_when_max_items_reached(self, monkeypatch):
        # kills Eq_Lt on `remaining == 0` (mutant `<` would not break).
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_PAGE_DELAY_S", 0.0)
        monkeypatch.setattr(config, "TOPCV_SCRAPE_MICROS_PER_ITEM", 1000)

        async def _fake_search(_kw, _page):
            return "<html/>"

        async def _fake_detail(_url):
            return {"skills": ["x"]}

        def _fake_parse(_html):
            return [
                {"source_url": f"https://www.topcv.vn/j/{i}", "salary_raw": ""}
                for i in range(5)
            ]

        monkeypatch.setattr(scraper, "_fetch_search_page", _fake_search)
        monkeypatch.setattr(scraper, "_fetch_detail_page", _fake_detail)
        monkeypatch.setattr(scraper, "_parse_search_page", _fake_parse)

        out = await scrape_topcv({"keyword": "x", "max_items": 2, "max_pages": 1})
        assert out["total_items"] == 2
        assert out["degraded"] is False

    @pytest.mark.asyncio
    async def test_success_degraded_false(self, monkeypatch):
        # kills ReplaceTrueWithFalse on `"degraded": False`.
        import app.proprietary.platforms.topcv.scraper as scraper

        monkeypatch.setattr(config, "TOPCV_PAGE_DELAY_S", 0.0)
        monkeypatch.setattr(config, "TOPCV_SCRAPE_MICROS_PER_ITEM", 1000)

        async def _fake_search(_kw, _page):
            return "<html/>"

        async def _fake_detail(_url):
            return {"skills": ["x"]}

        monkeypatch.setattr(scraper, "_fetch_search_page", _fake_search)
        monkeypatch.setattr(scraper, "_fetch_detail_page", _fake_detail)
        monkeypatch.setattr(scraper, "_parse_search_page", lambda _h: _many_cards(1))

        out = await scrape_topcv({"keyword": "x", "max_items": 1, "max_pages": 1})
        assert out["degraded"] is False
        assert out["degradation_reason"] is None
        assert out["total_items"] == 1
