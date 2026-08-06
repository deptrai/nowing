"""Unit tests for masothue.com parsers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.proprietary.platforms.masothue.parsers import (
    apply_detail,
    parse_detail_table,
    parse_search_results,
)
from app.proprietary.platforms.masothue.schemas import MasothueCompany

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_search_results() -> None:
    html = (FIXTURES / "search_page.html").read_text()
    results = parse_search_results(html)
    assert len(results) == 2
    assert results[0].name == "Công ty TNHH Vinamilk Tân Sơn"
    assert results[0].tax_code == "0314539064"
    assert results[0].legal_representative == "Nguyễn Văn A"
    assert results[0].detail_url == "https://masothue.com/0314539064-cong-ty-tnhh-vinamilk-tan-son"
    assert results[1].tax_code == "0314539065"


def test_parse_search_results_empty() -> None:
    results = parse_search_results("<html></html>")
    assert results == []


def test_parse_detail_table() -> None:
    html = (FIXTURES / "detail_page.html").read_text()
    data = parse_detail_table(html, include_phone=True)
    assert data["tax_code"] == "0314539064"
    assert data["tax_address"] == "10 Đường 3/2"
    assert data["address"] == "10 Đường 3/2, P. 12, Q. 10, TP. HCM"
    assert data["status"] == "Đang hoạt động"
    assert data["legal_representative"] == "Nguyễn Văn A"
    assert data["company_type"] == "Công ty TNHH"
    assert data["main_industry"] == "Sản xuất sữa"
    assert data["phone"] == "028 1234 5678"


def test_parse_detail_table_excludes_phone() -> None:
    html = (FIXTURES / "detail_page.html").read_text()
    data = parse_detail_table(html, include_phone=False)
    assert "phone" not in data


def test_apply_detail() -> None:
    html = (FIXTURES / "detail_page.html").read_text()
    company = MasothueCompany(
        name="Công ty TNHH Vinamilk Tân Sơn",
        tax_code="0314539064",
        detail_url="https://masothue.com/0314539064-cong-ty-tnhh-vinamilk-tan-son",
    )
    result = apply_detail(company, html, include_phone=True)
    assert result.tax_code == "0314539064"
    assert result.address == "10 Đường 3/2, P. 12, Q. 10, TP. HCM"
    assert result.main_industry == "Sản xuất sữa"
    assert result.phone == "028 1234 5678"
