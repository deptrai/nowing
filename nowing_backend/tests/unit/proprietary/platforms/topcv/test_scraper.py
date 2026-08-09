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
    _fetch_detail_page,
    _fetch_search_page,
    _parse_detail_markdown,
    _parse_search_page,
    _record_failure,
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
