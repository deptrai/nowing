"""Unit tests for ``app.proprietary.platforms.topcv`` scraper (Story 12.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.proprietary.platforms.topcv.scraper import (
    _parse_detail_markdown,
    _parse_search_page,
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
        assert out["degradation_reason"] == "anti_bot_block"
