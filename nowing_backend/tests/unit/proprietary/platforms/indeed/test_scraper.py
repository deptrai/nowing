"""Unit tests for ``app.proprietary.platforms.indeed`` scraper (Story 2.6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.proprietary.platforms.indeed.scraper import (
    _extract_salary_numbers,
    _parse_detail_markdown,
    _parse_search_page,
    scrape_indeed,
)

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _search_html() -> str:
    return _load("search-page.html")


def _detail_markdown() -> str:
    return _load("detail-markdown.txt")


class TestSearchPageParser:
    """AC-1: maps Indeed search HTML fields to normalized JobItem."""

    def test_extracts_job_cards(self):
        cards = _parse_search_page(_search_html())
        assert len(cards) > 0

    def test_maps_required_fields(self):
        cards = _parse_search_page(_search_html())
        item = cards[0]
        assert item["id"] == "indeed:91817aa16b89d707"
        assert item["title"] == "Data Engineer"
        assert item["company"] == "Freudenberg-NOK General Partnership"
        assert item["location"] == "Hybrid work in Plymouth, MI"
        assert item["source"] == "indeed"
        assert "/viewjob?jk=" in item["source_url"]
        assert "91817aa16b89d707" in item["source_url"]

    def test_filters_benefit_tags(self):
        cards = _parse_search_page(_search_html())
        summary = cards[0]["skills"]
        assert "Health insurance" in summary
        assert "401(k) matching" in summary


class TestDetailParser:
    """AC-2: maps Indeed detail markdown to normalized fields."""

    def test_parses_detail_markdown(self):
        detail = _parse_detail_markdown(_detail_markdown(), {})
        assert "Build scalable" in detail["job_description"]
        assert "Degree in Computer Science" in detail["job_requirement"]
        assert "401K Match" in detail["benefits"]
        assert detail["salary_raw"] and "$120,000" in detail["salary_raw"]

    def test_extracts_salary_range_and_period(self):
        assert _extract_salary_numbers("$120,000 a year") == (120000, None, "USD", "year")
        assert _extract_salary_numbers("$50 - $70 an hour") == (50, 70, "USD", "hour")
        assert _extract_salary_numbers("From $120,000")[0] == 120000


class TestScraperOrchestration:
    """AC-1: fetches Indeed search + detail pages."""

    @pytest.mark.asyncio
    async def test_returns_items_with_detail(self, monkeypatch):
        detail = _parse_detail_markdown(_detail_markdown(), {})

        async def _fake_search(
            keyword: str,
            location: str,
            radius: int,
            sort: str,
            start: int,
        ) -> str:
            return _search_html()

        async def _fake_detail(url: str) -> dict[str, Any]:
            return detail

        monkeypatch.setattr(
            "app.proprietary.platforms.indeed.scraper._fetch_search_page", _fake_search
        )
        monkeypatch.setattr(
            "app.proprietary.platforms.indeed.scraper._fetch_detail_page", _fake_detail
        )

        out = await scrape_indeed(
            {"keyword": "data engineer", "max_items": 1, "max_pages": 1}
        )

        assert out["degraded"] is False
        assert out["total_items"] == 1
        item = out["items"][0]
        assert item["title"] == "Data Engineer"
        assert "Degree in Computer Science" in item["job_requirement"]
        assert "401K Match" in item["benefits"]

    @pytest.mark.asyncio
    async def test_respects_max_items(self, monkeypatch):
        search_html = _search_html()
        detail = _parse_detail_markdown(_detail_markdown(), {})

        async def _fake_search(
            keyword: str,
            location: str,
            radius: int,
            sort: str,
            start: int,
        ) -> str:
            return search_html

        async def _fake_detail(url: str) -> dict[str, Any]:
            return detail

        monkeypatch.setattr(
            "app.proprietary.platforms.indeed.scraper._fetch_search_page", _fake_search
        )
        monkeypatch.setattr(
            "app.proprietary.platforms.indeed.scraper._fetch_detail_page", _fake_detail
        )

        out = await scrape_indeed(
            {"keyword": "data engineer", "max_items": 2, "max_pages": 1}
        )

        assert len(out["items"]) == 2


class TestScraperFailureModes:
    """AC-3: handles anti-bot blocks."""

    @pytest.mark.asyncio
    async def test_degrades_on_empty(self, monkeypatch):
        async def _fake_search(
            keyword: str,
            location: str,
            radius: int,
            sort: str,
            start: int,
        ) -> str:
            return ""

        monkeypatch.setattr(
            "app.proprietary.platforms.indeed.scraper._fetch_search_page", _fake_search
        )

        out = await scrape_indeed(
            {"keyword": "data engineer", "max_items": 1, "max_pages": 1}
        )

        assert out["degraded"] is True
        assert out["degradation_reason"] == "anti_bot_block"
