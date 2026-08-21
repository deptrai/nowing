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
    assert (
        results[0].detail_url
        == "https://masothue.com/0314539064-cong-ty-tnhh-vinamilk-tan-son"
    )
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


def test_parse_detail_table_excludes_phone_by_default() -> None:
    html = (FIXTURES / "detail_page.html").read_text()
    data = parse_detail_table(html)
    assert "phone" not in data


def test_apply_detail_excludes_phone_by_default() -> None:
    html = (FIXTURES / "detail_page.html").read_text()
    company = MasothueCompany(
        name="Công ty TNHH Vinamilk Tân Sơn",
        tax_code="0314539064",
    )
    res = apply_detail(company, html)
    assert res.phone is None
    assert res.rep_phone is None


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
    assert result.representative == "Nguyễn Văn A"
    assert result.rep_phone == "028 1234 5678"
    assert result.main_business == "Sản xuất sữa"
    assert result.founding_date == "2010-01-01"


def test_apply_detail_preserves_existing_aliases() -> None:
    html = "<table class='table-taxinfo'><tr><th>Địa chỉ</th><td>New Address</td></tr></table>"
    company = MasothueCompany(
        name="Vinamilk",
        tax_code="0314539064",
        representative="Existing Rep",
        rep_phone="0909090909",
        main_business="Existing Business",
        founding_date="2000-01-01",
    )
    res = apply_detail(company, html, include_phone=True)
    assert res.representative == "Existing Rep"
    assert res.rep_phone == "0909090909"
    assert res.main_business == "Existing Business"
    assert res.founding_date == "2000-01-01"
    assert res.address == "New Address"


def test_apply_detail_empty_html_returns_unchanged() -> None:
    company = MasothueCompany(name="Vinamilk", tax_code="0314539064")
    res = apply_detail(company, "<html></html>")
    assert res.name == "Vinamilk"
    assert res.address is None


def test_apply_detail_generates_slug_url_when_missing() -> None:
    company = MasothueCompany(
        name="Công ty TNHH Vinamilk", tax_code="0314539064", detail_url=None
    )
    table_html = (
        "<table class='table-taxinfo'><tr><th>Địa chỉ</th><td>Hà Nội</td></tr></table>"
    )
    res = apply_detail(company, table_html)
    assert res.detail_url is not None
    assert res.detail_url.startswith("https://masothue.com/0314539064-")

    # When detail_url already exists, it is preserved
    c2 = MasothueCompany(
        name="Vinamilk", tax_code="0314539064", detail_url="https://existing.com/1"
    )
    res2 = apply_detail(c2, table_html)
    assert res2.detail_url == "https://existing.com/1"


def test_normalize_key_helper() -> None:
    from app.proprietary.platforms.masothue.parsers import _normalize_key

    assert _normalize_key(None) is None
    assert _normalize_key("") is None
    assert _normalize_key("Mã số thuế:") == "tax_code"
    assert _normalize_key("Loại hình DN") == "company_type"
    assert _normalize_key("Loại hình doanh nghiệm") == "company_type"
    assert _normalize_key("Loại hình doanh nghiệp") == "company_type"
    assert _normalize_key("Vốn điều lệ (VNĐ)") == "charter_capital"
    assert _normalize_key("Vốn điều lệ") == "charter_capital"
    assert _normalize_key("Unknown Label") is None


def test_clean_text_helper() -> None:
    from app.proprietary.platforms.masothue.parsers import _clean_text

    assert _clean_text(None) is None
    assert _clean_text("   ") is None
    assert _clean_text("  hello   world \n test ") == "hello world test"


def test_absolute_url_helper() -> None:
    from app.proprietary.platforms.masothue.parsers import _absolute_url

    assert _absolute_url(None) is None
    assert _absolute_url("") is None
    assert _absolute_url("https://masothue.com/abc") == "https://masothue.com/abc"
    assert _absolute_url("http://other.com/abc") == "http://other.com/abc"
    assert _absolute_url("/0314539064-slug") == "https://masothue.com/0314539064-slug"


def test_parse_detail_table_drops_ad_rows_and_continues() -> None:
    html = """
    <table class="table-taxinfo">
        <tr><th>  Thông tin  </th><td>Cập nhật mã số thuế cho doanh nghiệp</td></tr>
        <tr><th>  Mã số thuế  </th><td>0314539064</td></tr>
        <tr><th>  Góp ý  </th><td>Nếu bạn có đề xuất gì liên hệ</td></tr>
        <tr><th>  Địa chỉ  </th><td>10 Đường 3/2</td></tr>
        <tr><th></th><td>Invalid row without th</td></tr>
        <tr><th>Invalid</th><td></td></tr>
    </table>
    """
    data = parse_detail_table(html)
    assert data["tax_code"] == "0314539064"
    assert data["address"] == "10 Đường 3/2"


def test_extract_tax_code_and_representative_helpers() -> None:
    from app.proprietary.platforms.masothue.parsers import (
        _extract_representative,
        _extract_tax_code,
    )

    assert _extract_tax_code("") is None
    assert _extract_tax_code("Mã số thuế: 031-453-9064-001") == "0314539064001"
    assert _extract_tax_code("No tax info") is None

    assert _extract_representative("") is None
    assert (
        _extract_representative("Người đại diện: Nguyễn Văn A Mã số thuế: 0314539064")
        == "Nguyễn Văn A"
    )
    assert _extract_representative("Người đại diện: Trần Thị B") == "Trần Thị B"
    assert _extract_representative("No rep info") is None


def test_parse_pagination_branches() -> None:
    from app.proprietary.platforms.masothue.parsers import parse_pagination

    html = """
    <div class="pagination">
        <span class="page-numbers current">2</span>
        <a class="page-numbers" href="?page=1">1</a>
        <span class="page-numbers dots">...</span>
        <a class="page-numbers" href="?page=3">3</a>
        <a class="page-numbers" href="?page=4">4</a>
    </div>
    """
    cur, nxt = parse_pagination(html)
    assert cur == 2
    assert nxt == 3

    html_last = """
    <div class="pagination">
        <a class="page-numbers" href="?page=4">4</a>
        <span class="page-numbers current">5</span>
    </div>
    """
    cur_last, nxt_last = parse_pagination(html_last)
    assert cur_last == 5
    assert nxt_last is None

    assert parse_pagination("<html></html>") == (1, None)


def test_extract_city_district_from_address() -> None:
    from app.proprietary.platforms.masothue.parsers import (
        _extract_city_district_from_address,
    )

    assert _extract_city_district_from_address(None) == (None, None)
    assert _extract_city_district_from_address("") == (None, None)

    # Address with exactly 2 parts (kills i > 0 -> i > 1 mutant)
    city_2p, dist_2p = _extract_city_district_from_address("Phường 12, Quận 10")
    assert city_2p == "Quận 10"
    assert dist_2p == "Phường 12"

    _city, dist = _extract_city_district_from_address(
        "Số 10 Đường 3/2, Phường 12, Quận 10, Hồ Chí Minh"
    )
    assert dist == "Phường 12"

    city_single, dist_single = _extract_city_district_from_address("Hồ Chí Minh")
    assert city_single == "Hồ Chí Minh"
    assert dist_single is None

    city_fb, dist_fb = _extract_city_district_from_address(
        "Số 10 Đường ABC, Huyện Châu Thành, Tỉnh Lạ"
    )
    assert dist_fb == "Huyện Châu Thành"
    assert city_fb == "Tỉnh Lạ"

    city_fb_end, dist_fb_end = _extract_city_district_from_address(
        "Số 10 Đường ABC, Huyện Châu Thành"
    )
    assert dist_fb_end == "Huyện Châu Thành"
    assert city_fb_end is None

    assert _extract_city_district_from_address("Số 10 Đường ABC") == (None, None)


def test_parse_search_results_deduplicates_within_page_and_continues() -> None:
    html = """
    <div>
        <div><h3>Invalid card with no link</h3></div>
        <div><h3><a></a></h3></div>
        <div><h3><a href="/0314539064-slug">Công ty Vinamilk</a></h3><p>Mã số thuế: 0314539064</p></div>
        <div><h3><a href="/0314539064-slug">Công ty Vinamilk</a></h3><p>Mã số thuế: 0314539064</p></div>
        <div><h3><a href="/0314539065-slug">Công ty Vinamilk 2</a></h3><p>Mã số thuế: 0314539065</p></div>
        <div><h3><a href="/other-url-1">Công ty Không Thuế</a></h3></div>
        <div><h3><a href="/other-url-2">Công ty Không Thuế</a></h3></div>
        <div><h3><a href="/url-same">Công ty Thuế A</a></h3><p>Mã số thuế: 111</p></div>
        <div><h3><a href="/url-same">Công ty Thuế B</a></h3><p>Mã số thuế: 222</p></div>
    </div>
    """
    results = parse_search_results(html)
    assert len(results) == 6
    names = [r.name for r in results]
    assert "Công ty Vinamilk" in names
    assert "Công ty Vinamilk 2" in names
    assert "Công ty Không Thuế" in names
    assert "Công ty Thuế A" in names
    assert "Công ty Thuế B" in names


def test_parse_detail_table_empty_and_continue_after_invalid_rows() -> None:
    assert parse_detail_table("<html><body>No table here</body></html>") == {}

    html = """
    <table class="table-taxinfo">
        <tr><td>No TH</td></tr>
        <tr><th></th><td>Empty TH</td></tr>
        <tr><th>Mã số thuế</th><td></td></tr>
        <tr><th>Thông tin</th><td>Cập nhật mã số thuế cho doanh nghiệp</td></tr>
        <tr><th>Góp ý</th><td>Nếu bạn có đề xuất gì vui lòng gửi</td></tr>
        <tr><th>Địa chỉ</th><td>Số 10 Đường 3/2</td></tr>
        <tr><th>Mã số thuế</th><td>0314539064</td></tr>
    </table>
    """
    data = parse_detail_table(html)
    assert data["address"] == "Số 10 Đường 3/2"
    assert data["tax_code"] == "0314539064"
