"""ITviec server-rendered HTML parser."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from lxml import html as lxml_html

from app.config import config

logger = logging.getLogger(__name__)

_BASE_URL = "https://itviec.com"

_SALARY_PERIOD_RE = re.compile(r"\b(tháng|month|năm|year|giờ|hour|ngày|day)\b", re.IGNORECASE)
_AGE_RE = re.compile(r"Posted\s+(\d+)\s+(hour|hours|day|days|week|weeks|month|months)\s+ago", re.IGNORECASE)


def _degraded(reason: str, *, cost_micros: int = 0) -> dict[str, Any]:
    return {
        "items": [],
        "cost_micros": cost_micros,
        "degraded": True,
        "degradation_reason": reason,
        "total_items": 0,
    }


def _safe_text(element: Any) -> str | None:
    if element is None:
        return None
    text = " ".join(element.itertext())
    return text.strip() or None


def _normalize_keyword(value: str) -> str:
    """Convert a search phrase into an ITviec URL slug."""
    text = re.sub(r"[^a-z0-9\s-]", "", value.lower())
    text = re.sub(r"\s+", "-", text.strip())
    return text.strip("-") or "it"


def _extract_salary_numbers(text: str) -> tuple[int | None, int | None, str, str | None]:
    """Parse a free-form salary string into (min, max, currency, period_tag).

    Returns integers in the raw currency unit (VND for Vietnamese postings).
    """
    if not text:
        return None, None, "VND", None

    lower = text.lower()
    if any(k in lower for k in ("sign in to view", "thương lượng", "thoả thuận", "negotiable")):
        return 0, 0, "VND", "negotiable"

    currency = "VND"
    if any(c in text for c in ("$", "usd")):
        currency = "USD"

    period_tag: str | None = None
    pm = _SALARY_PERIOD_RE.search(text)
    if pm:
        token = pm.group(1).lower()
        if token in ("tháng", "month"):
            period_tag = "month"
        elif token in ("năm", "year"):
            period_tag = "year"
        elif token in ("giờ", "hour"):
            period_tag = "hour"
        elif token in ("ngày", "day"):
            period_tag = "day"

    # Find numeric ranges, tolerating Vietnamese separators.
    numbers: list[float] = []
    for token in re.findall(r"[\d\.,]+\s*[kKmMbBtT]?", text):
        token = token.strip().replace(",", "")
        unit = 1.0
        if token[-1:].lower() in ("k", "tr", "m", "triệu"):
            unit = 1_000 if token[-1:].lower() == "k" else 1_000_000
            token = token[:-1].strip()
        try:
            numbers.append(float(token) * unit)
        except ValueError:
            continue

    if not numbers:
        return 0, 0, currency, period_tag or "month"

    # Determine direction from key phrases.
    min_v: int | None = int(numbers[0])
    max_v: int | None = int(numbers[-1]) if len(numbers) > 1 else None
    if "tới" in lower or "up to" in lower:
        min_v, max_v = 0, int(numbers[0])
    elif "từ" in lower or "from" in lower:
        min_v = int(numbers[0])
        max_v = None
    return min_v, max_v, currency, period_tag or "month"


def _parse_posted(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    from datetime import UTC, datetime, timedelta

    m = _AGE_RE.search(text)
    if not m:
        return None
    amount = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("hour"):
        delta = timedelta(hours=amount)
    elif unit.startswith("day"):
        delta = timedelta(days=amount)
    elif unit.startswith("week"):
        delta = timedelta(weeks=amount)
    elif unit.startswith("month"):
        delta = timedelta(days=amount * 30)
    else:
        return None
    return (datetime.now(UTC) - delta).isoformat()


def _abs_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return urljoin(_BASE_URL, path)


def _clean_url(url: str) -> str:
    """Drop preview/lab query params and /content suffix for ITviec URLs."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path
    if path.endswith("/content"):
        path = path[:-8]
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _html_text_without_heading(div: Any, heading: str) -> str:
    """Return the text of ``div`` minus its first ``h2`` heading text."""
    full = _safe_text(div) or ""
    if heading and full.startswith(heading):
        return full[len(heading):].strip()
    return full


def _parse_detail(html: str, source_url: str) -> dict[str, Any]:
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return {}

    # Title: full JD page uses h1 inside .job-header-info; preview uses h2.text-it-black.
    title_els = root.xpath('//div[contains(@class,"job-header-info")]//h1')
    if not title_els:
        title_els = root.xpath('//h1 | //h2[contains(@class,"text-it-black")] | //h2')
    title = _safe_text(title_els[0]) if title_els else ""

    # Company: full page uses .employer-name; preview uses a.company or .text-rich-grey company link.
    company = ""
    for sel in (
        '//div[contains(@class,"employer-name")]',
        '//h3/a[contains(@href,"/companies/")]',
        '//a[contains(@href,"/companies/") and contains(@class,"text-rich-grey")]',
        '//div[contains(@class,"preview-job-header")]//a[contains(@href,"/companies/")]',
    ):
        for company_el in root.xpath(sel):
            company = _safe_text(company_el) or ""
            if company:
                break
        if company:
            break

    # Overview section: location, work mode, posted time, skills, domain.
    overview = root.xpath(
        '//section[contains(@class,"preview-job-overview") or contains(@class,"job-show-info")]'
    )
    overview_root = overview[0] if overview else root

    location = None
    work_mode = None
    posted_text = None
    for span in overview_root.xpath('.//span[contains(@class,"text-rich-grey")] | .//div[contains(@class,"text-rich-grey") and @title]'):
        text = _safe_text(span) or ""
        if not location and any(k in text for k in ("Hà Nội", "Ha Noi", "Hồ Chí Minh", "Ho Chi Minh", "Đà Nẵng", "Da Nang", "phố", "đường", "tầng", "tòa nhà")):
            location = text
        if not work_mode and text in ("At office", "Remote", "Hybrid"):
            work_mode = text
        if not posted_text and ("ago" in text or any(k in text for k in ("hour", "day", "week", "month"))):
            posted_text = text

    # Skills appear as tag links under the overview.
    skills: list[str] = []
    for a in overview_root.xpath('.//a[contains(@class,"itag-light") and contains(@href,"/it-jobs/")]'):
        skill = _safe_text(a)
        if skill and skill not in skills:
            skills.append(skill)

    # Job domain tags are non-link itags.
    job_domain: list[str] = []
    for div in overview_root.xpath('.//div[contains(@class,"itag") and contains(@class,"cursor-default")]'):
        domain = _safe_text(div)
        if domain and domain not in job_domain:
            job_domain.append(domain)

    # JD and requirements live in .paragraph divs (inside section.job-description/job-experiences
    # in the content endpoint, or directly with an h2 heading in the full page).
    jd: str | None = None
    req: str | None = None

    for section in root.xpath(
        '//section[contains(@class,"job-description")] | //section[contains(@class,"job-experiences")]'
    ):
        heading = _safe_text(section.xpath('.//h2[1]')[0]) if section.xpath('.//h2[1]') else ""
        content_els = section.xpath('.//div[contains(@class,"paragraph")]')
        content = _safe_text(content_els[0]) if content_els else ""
        if heading and "Job description" in heading:
            jd = content
        elif heading and ("skills and experience" in heading or "yêu cầu" in heading.lower()):
            req = content

    if jd is None or req is None:
        for div in root.xpath('//div[contains(@class,"paragraph") and h2]'):
            heading_els = div.xpath('.//h2')
            heading = _safe_text(heading_els[0]) if heading_els else ""
            if jd is None and heading and "Job description" in heading:
                jd = _html_text_without_heading(div, heading)
            elif req is None and heading and ("skills and experience" in heading or "yêu cầu" in heading.lower()):
                req = _html_text_without_heading(div, heading)

    return {
        "title": title,
        "company": company,
        "location": location,
        "work_mode": work_mode,
        "posted_text": posted_text,
        "skills": skills,
        "job_domain": job_domain,
        "job_description": jd or "",
        "job_requirement": req or "",
    }


def _parse_search_page(html: str) -> list[dict[str, Any]]:
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return []

    cards = root.xpath('//div[contains(@class,"job-card") and contains(@class,"ipt-2")]')
    results: list[dict[str, Any]] = []

    for card in cards:
        slug = card.get("data-search--job-selection-job-slug-value", "")
        detail_rel = card.get("data-search--job-selection-job-url-value", "") or ""
        detail_url = _clean_url(_abs_url(detail_rel))

        title = ""
        title_link = card.xpath('.//h3/a[contains(@class,"text-it-black")]')
        if title_link:
            title = _safe_text(title_link[0]) or ""

        company = ""
        company_link = card.xpath('.//a[contains(@href,"/companies/") and contains(@class,"text-rich-grey")]')
        if company_link:
            company = _safe_text(company_link[0]) or ""

        location = None
        for loc in card.xpath('.//div[contains(@class,"text-rich-grey") and @title]'):
            location = loc.get("title") or _safe_text(loc)
            if location:
                break

        salary_raw = ""
        salary_el = card.xpath('.//div[contains(@class,"salary")]')
        if salary_el:
            salary_raw = _safe_text(salary_el[0]) or ""

        posted = None
        for posted_el in card.xpath('.//span[contains(@class,"small-text") and contains(@class,"text-dark-grey")]'):
            posted = _safe_text(posted_el)
            if posted:
                break

        skills: list[str] = []
        for a in card.xpath('.//a[contains(@class,"itag-light") and contains(@data-responsive-tag-list-target,"tag")]'):
            skill = _safe_text(a)
            if skill and skill not in skills:
                skills.append(skill)

        canonical = _clean_url(_abs_url(detail_rel.split("?")[0])) if detail_rel else ""
        detail_url = canonical.replace("https://itviec.com", "") + "/content" if canonical else ""
        if detail_url.startswith("/"):
            detail_url = f"https://itviec.com{detail_url}"
        else:
            detail_url = canonical

        results.append({
            "id": f"itviec:{slug or canonical}",
            "title": title,
            "company": company,
            "location": location,
            "source_url": canonical,
            "salary_raw": salary_raw,
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "salary_period_id": None,
            "employment_type": None,
            "experience_years": None,
            "job_description": "",
            "job_requirement": "",
            "skills": skills,
            "posted_at": _parse_posted(posted),
            "is_active": True,
            "source": "itviec",
            "_detail_url": detail_url,
        })

    return results


def _apply_detail(item: dict[str, Any], detail: dict[str, Any]) -> None:
    if detail.get("title"):
        item["title"] = detail["title"]
    if detail.get("company"):
        item["company"] = detail["company"]
    if detail.get("location"):
        item["location"] = detail["location"]
    item["job_description"] = detail.get("job_description", "")
    item["job_requirement"] = detail.get("job_requirement", "")
    if detail.get("work_mode"):
        item["employment_type"] = _map_work_mode(detail["work_mode"])
    if detail.get("skills"):
        item["skills"] = detail["skills"]
    if detail.get("posted_text"):
        item["posted_at"] = _parse_posted(detail["posted_text"]) or item.get("posted_at")
    item["job_domain"] = detail.get("job_domain", [])

    salary_raw = item.get("salary_raw") or ""
    if salary_raw and "sign in" in salary_raw.lower():
        item["salary_min"] = 0
        item["salary_max"] = 0
        item["salary_currency"] = "VND"
        item["salary_period_id"] = "hidden"
    else:
        min_v, max_v, currency, period = _extract_salary_numbers(salary_raw)
        item["salary_min"] = min_v
        item["salary_max"] = max_v
        item["salary_currency"] = currency
        item["salary_period_id"] = period


def _map_work_mode(mode: str) -> str | None:
    lower = mode.lower()
    if "remote" in lower:
        return "remote"
    if "hybrid" in lower:
        return "hybrid"
    if any(k in lower for k in ("office", "onsite", "at office", "tại văn phòng")):
        return "full_time"
    return None


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


async def _do_search(client: httpx.AsyncClient, keyword: str, page: int) -> httpx.Response:
    url = f"{_BASE_URL}/it-jobs/{_normalize_keyword(keyword)}"
    if page > 1:
        url = f"{url}?page={page}"
    return await client.get(url, headers=_headers(), timeout=config.ITVIEC_TIMEOUT_S)


async def _do_detail(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await client.get(url, headers=_headers(), timeout=config.ITVIEC_TIMEOUT_S)


async def _scrape(params: dict[str, Any]) -> dict[str, Any]:
    max_items = int(params.get("max_items", 50) or 0)
    starting_page = int(params.get("page", 1) or 1)
    default_max_pages = 1 if "page" in params else config.ITVIEC_MAX_PAGES
    max_pages = int(params.get("max_pages", default_max_pages) or 1)

    if max_items == 0 or max_pages == 0:
        return {
            "items": [],
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 0,
        }

    keyword = params.get("keyword", "data engineer")
    items: list[dict[str, Any]] = []
    cost_micros = 0

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for page in range(starting_page, starting_page + max_pages):
            remaining = max(0, max_items - len(items))
            if remaining == 0:
                break

            resp = await _do_search(client, keyword, page)

            if resp.status_code == 429:
                return _degraded("rate_limited", cost_micros=cost_micros)
            if resp.status_code in (403, 451):
                return _degraded("access_blocked", cost_micros=cost_micros)
            if resp.status_code >= 500:
                return _degraded("api_error", cost_micros=cost_micros)
            resp.raise_for_status()

            cards = _parse_search_page(resp.text)
            if not cards:
                break

            for card in cards[:remaining]:
                detail_resp = await _do_detail(client, card["_detail_url"])
                if detail_resp.status_code == 200:
                    detail = _parse_detail(detail_resp.text, card["_detail_url"])
                    _apply_detail(card, detail)
                    cost_micros += config.ITVIEC_SCRAPE_MICROS_PER_ITEM
                    del card["_detail_url"]
                    items.append(card)
                else:
                    # Detail fetch failed; keep the search card with low confidence but bill it.
                    _apply_detail(card, {})
                    cost_micros += config.ITVIEC_SCRAPE_MICROS_PER_ITEM
                    del card["_detail_url"]
                    items.append(card)

                if len(items) >= max_items:
                    break

                await asyncio.sleep(config.ITVIEC_PAGE_DELAY_S)

            if len(items) >= max_items:
                break
            await asyncio.sleep(config.ITVIEC_PAGE_DELAY_S)

    return {
        "items": items,
        "cost_micros": cost_micros,
        "degraded": False,
        "degradation_reason": None,
        "total_items": len(items),
    }


async def scrape_itviec(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch and parse ITviec job search + detail pages."""
    try:
        return await _scrape(params)
    except httpx.TimeoutException:
        return _degraded("timeout")
    except httpx.ConnectError:
        return _degraded("api_error")
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 429:
            return _degraded("rate_limited")
        if code in (403, 451):
            return _degraded("access_blocked")
        if code >= 500:
            return _degraded("api_error")
        return _degraded("api_error")
    except Exception as exc:
        logger.warning("itviec.scrape failed: %s", exc)
        return _degraded("api_error")
