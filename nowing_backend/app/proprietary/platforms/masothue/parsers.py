"""Pure, I/O-free parsing of masothue.com HTML pages."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .schemas import MasothueCompany

_ORIGIN = "https://masothue.com"

# Vietnamese table labels -> schema keys
_DETAIL_LABEL_MAP = {
    "mã số thuế": "tax_code",
    "địa chỉ thuế": "tax_address",
    "địa chỉ": "address",
    "tình trạng": "status",
    "tên quốc tế": "international_name",
    "tên viết tắt": "short_name",
    "người đại diện": "legal_representative",
    "điện thoại": "phone",
    "ngày hoạt động": "active_date",
    "quản lý bởi": "managed_by",
    "loại hình dn": "company_type",
    "loại hình doanh nghiệm": "company_type",
    "loại hình doanh nghiệp": "company_type",
    "ngành nghề chính": "main_industry",
}

_TAX_CODE_RE = re.compile(r"Mã\s+số\s+thuế[:\s]*([\d\-]{10,})", re.IGNORECASE)
_REP_RE = re.compile(
    r"Người\s+đại\s+diện[:\s]*(.+?)(?=\s*(?:Mã\s+số\s+thuế|Điện\s+thoại|Địa\s+chỉ(?:\s+thuế)?|Tình\s+trạng|Tên\s+quốc\s+tế|Tên\s+viết\s+tắt|Ngày\s+hoạt\s+động|Quản\s+lý\s+bởi|Loại\s+hình\s+(?:DN|doanh\s+nghiệ[mp])|Ngành\s+nghề\s+chính)|$)",
    re.IGNORECASE,
)


def _normalize_key(label: str | None) -> str | None:
    if not label:
        return None
    normalized = label.strip().lower()
    # Drop trailing colon if any
    normalized = normalized.rstrip(":")
    return _DETAIL_LABEL_MAP.get(normalized)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())
    return cleaned if cleaned else None


def _absolute_url(href: str | None) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith("http"):
        return href
    return urljoin(_ORIGIN, href)


def parse_detail_table(html: str, include_phone: bool = False) -> dict[str, Any]:
    """Parse ``table.table-taxinfo`` from a masothue detail page."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.table-taxinfo")
    if table is None:
        return {}

    data: dict[str, Any] = {}
    for row in table.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if not th or not td:
            continue

        key = _normalize_key(th.get_text(strip=True))
        if key is None:
            continue

        value = _clean_text(td.get_text(" ", strip=True))
        if value is None:
            continue

        # Drop ad/upsell rows masquerading as data.
        if "cập nhật mã số thuế" in value.lower():
            continue
        if "nếu bạn có đề xuất" in value.lower():
            continue

        if key == "phone" and not include_phone:
            continue

        data[key] = value

    # If the address row has a more specific tax_address sibling, keep both.
    return data


def _extract_tax_code(text: str) -> str | None:
    if not text:
        return None
    for match in _TAX_CODE_RE.finditer(text):
        code = match.group(1).strip()
        if code:
            return code.replace("-", "")
    return None


def _extract_representative(text: str) -> str | None:
    if not text:
        return None
    m = _REP_RE.search(text)
    if m:
        return _clean_text(m.group(1))
    return None


def _parse_search_result_card(card: Any, base_url: str = _ORIGIN) -> MasothueCompany | None:
    """Map one search-result card (``h3 > a`` + metadata) to a typed company."""
    link = card.find("h3")
    if not link:
        return None
    a = link.find("a")
    if not a:
        return None

    name = _clean_text(a.get_text(strip=True))
    detail_path = a.get("href")
    detail_url = _absolute_url(detail_path)

    if not name:
        return None

    # Tax code and representative are in the text following the title.
    siblings_text = " ".join(p.get_text(" ", strip=True) for p in card.find_all(["p", "div"]))
    tax_code = _extract_tax_code(siblings_text)
    legal_representative = _extract_representative(siblings_text)

    return MasothueCompany(
        dataType="masothue_company",
        name=name,
        tax_code=tax_code,
        legal_representative=legal_representative,
        detail_url=detail_url,
    )


def parse_search_results(html: str) -> list[MasothueCompany]:
    """Parse the search result list from a masothue search page."""
    soup = BeautifulSoup(html, "lxml")
    cards: list[Any] = []

    # Primary: h3 > a[href]
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=True)
        if a:
            # Treat the h3's parent as the card so we can read surrounding text.
            cards.append(h3.parent or h3)

    results: list[MasothueCompany] = []
    seen: set[str] = set()
    for card in cards:
        company = _parse_search_result_card(card)
        if company is None or company.name is None:
            continue
        # Dedupe within the page by (name, tax_code) or by detail URL.
        key = f"{company.name or ''}|{company.tax_code or ''}|{company.detail_url or ''}"
        if key in seen:
            continue
        seen.add(key)
        results.append(company)

    return results


def parse_pagination(html: str) -> tuple[int, int | None]:
    """Return (current_page, next_page) from the page-numbers widget."""
    soup = BeautifulSoup(html, "lxml")
    current = 1
    pages: set[int] = set()

    for a in soup.select(".page-numbers"):
        text = a.get_text(strip=True)
        try:
            page = int(text)
        except ValueError:
            continue
        if "current" in (a.get("class") or []):
            current = page
        pages.add(page)

    next_pages = [p for p in pages if p > current]
    next_page = min(next_pages) if next_pages else None
    return current, next_page


def apply_detail(
    company: MasothueCompany,
    detail_html: str,
    *,
    include_phone: bool = False,
) -> MasothueCompany:
    """Enhance a search-result company with parsed detail-page data."""
    data = parse_detail_table(detail_html, include_phone=include_phone)
    if not data:
        # Detail page missing table -> skip enhancements.
        return company

    # Overwrite only when the detail provides a value.
    for key, value in data.items():
        if value:
            setattr(company, key, value)

    # Detail URL from the path if the company has none.
    if company.detail_url is None and company.tax_code and company.name:
        slug = re.sub(r"\s+", "-", company.name.strip().lower())
        slug = re.sub(r"[^\w\-]", "", slug)
        company.detail_url = f"{_ORIGIN}/{company.tax_code}-{slug}"

    return company
