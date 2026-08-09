"""Golden fixture regression tests for the TopCV scraper (AC-10).

These tests fail if the upstream HTML/markdown selectors drift from the
committed fixture files, catching structural changes before deployment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.proprietary.platforms.topcv.scraper import (
    _extract_salary_numbers,
    _parse_detail_markdown,
    _parse_search_page,
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


class TestGoldenSearchPage:
    """AC-10: search-page.html selectors must keep returning the expected cards."""

    def test_extracts_expected_number_of_job_cards(self):
        cards = _parse_search_page(_search_html())
        assert len(cards) == 50

    def test_first_card_has_required_fields(self):
        cards = _parse_search_page(_search_html())
        assert cards
        item = cards[0]

        assert item["id"] == "topcv:1599438"
        assert item["title"] == "ETL Developer - Data Engineer"
        assert item["company"] == "Công Ty TNHH LG CNS VIỆT NAM"
        assert item["location"] == "Hà Nội"
        assert "topcv.vn" in item["source_url"]
        assert "etl-developer-data-engineer/1599438.html" in item["source_url"]
        assert item["salary_raw"] == "Thoả thuận"
        assert item["salary_hidden"] is True
        assert item["salary_confidence"] == "low"
        assert item["salary_min"] == 0
        assert item["salary_max"] == 0
        assert item["salary_currency"] == "VND"
        assert item["salary_period_id"] == "negotiable"
        assert item["experience_years"] == 3
        assert item["source"] == "topcv"
        assert item["is_active"] is True

    def test_search_page_salary_parsing(self):
        """Salary confidence/hidden fields are populated for every card."""
        cards = _parse_search_page(_search_html())
        for card in cards:
            assert "salary_hidden" in card
            assert "salary_confidence" in card
            assert "salary_min" in card
            assert "salary_max" in card
            assert "salary_currency" in card
            assert "salary_period_id" in card


class TestGoldenDetailMarkdown:
    """AC-10: detail-markdown.txt must keep yielding the expected detail fields."""

    def test_extracts_description_requirements_and_location(self):
        detail = _parse_detail_markdown(_detail_markdown(), _detail_metadata())
        assert detail["job_description"]
        assert "Develop in web application" in detail["job_description"]
        assert detail["job_requirement"]
        assert "Bachelor" in detail["job_requirement"]
        assert detail["location"]
        assert "Hà Nội" in detail["location"]

    def test_extracts_employment_type_and_skills(self):
        detail = _parse_detail_markdown(_detail_markdown(), _detail_metadata())
        assert detail["employment_type"] == "full_time"
        assert "SQL" in detail["skills"]
        assert detail["experience_years"] == 3


class TestSalaryNumberExtraction:
    """AC-4: salary parser must expose hidden/confidence and common Vietnamese units."""

    def test_hidden_when_negotiation_keyword(self):
        assert _extract_salary_numbers("Thoả thuận") == (
            0,
            0,
            "VND",
            "negotiable",
            True,
            "low",
        )

    def test_parses_vietnamese_million_range(self):
        assert _extract_salary_numbers("25tr - 35tr / tháng") == (
            25_000_000,
            35_000_000,
            "VND",
            "month",
            False,
            "medium",
        )

    def test_parses_triệu(self):
        assert _extract_salary_numbers("15 triệu - 20 triệu") == (
            15_000_000,
            20_000_000,
            "VND",
            "month",
            False,
            "medium",
        )

    def test_low_confidence_when_no_numbers(self):
        assert _extract_salary_numbers("Competitive") == (
            0,
            0,
            "VND",
            "month",
            True,
            "low",
        )
