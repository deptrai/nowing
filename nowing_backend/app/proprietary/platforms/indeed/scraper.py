"""Indeed HTML fetcher with anti-bot handling."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote_plus, urlencode, urljoin, urlparse

from lxml import html as lxml_html
from scrapling.fetchers import StealthyFetcher

from app.config import config

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.indeed.com"

_SALARY_PERIOD_RE = re.compile(
    r"\b(hour|hours|hourly|day|days|daily|week|weeks|weekly|month|months|monthly|year|years|yearly)\b",
    re.IGNORECASE,
)
_AGE_RE = re.compile(
    r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago",
    re.IGNORECASE,
)
_EXP_RE = re.compile(
    r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
    re.IGNORECASE,
)

_MAJOR_SECTION_KEYWORDS = (
    "responsibilities",
    "about the job",
    "job description",
    "the role",
    "what you'll do",
    "qualifications",
    "requirements",
    "what you bring",
    "what you need",
    "what we're looking for",
    "some of your benefits",
    "benefits",
    "perks",
    "compensation & benefits",
    "compensation",
    "salary",
    "pay",
    "location",
    "work location",
    "job location",
    "employment type",
    "job type",
    "work schedule",
    "experience",
    "years of experience",
)


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
    """Convert a search phrase into an Indeed query slug."""
    text = re.sub(r"[^a-z0-9\s-]", "", value.lower())
    text = re.sub(r"\s+", " ", text.strip())
    return text.strip() or "data engineer"


def _search_url(
    keyword: str,
    location: str,
    radius: int,
    sort: str,
    start: int,
) -> str:
    """Build an Indeed search URL."""
    params: dict[str, str] = {"q": quote_plus(_normalize_keyword(keyword))}
    if location and location.strip():
        params["l"] = quote_plus(location.strip())
    if radius:
        params["radius"] = str(radius)
    if sort == "date":
        params["sort"] = "date"
    if start:
        params["start"] = str(start)
    return f"{_BASE_URL}/jobs?{urlencode(params)}"


def _clean_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _extract_salary_numbers(
    text: str,
) -> tuple[int | None, int | None, str, str | None]:
    """Parse a free-form Indeed salary string into (min, max, currency, period_tag)."""
    if not text:
        return None, None, "USD", None

    lower = text.lower()
    if any(
        k in lower
        for k in ("negotiable", "competitive", "depends on experience", "doe")
    ):
        return 0, 0, "USD", "negotiable"

    currency = "USD"
    if any(c in text for c in ("$", "usd")):
        currency = "USD"
    elif "£" in text or "gbp" in lower:
        currency = "GBP"
    elif "€" in text or "eur" in lower:
        currency = "EUR"

    period_tag: str | None = None
    pm = _SALARY_PERIOD_RE.search(text)
    if pm:
        token = pm.group(1).lower()
        if token in ("hour", "hours", "hourly"):
            period_tag = "hour"
        elif token in ("day", "days", "daily"):
            period_tag = "day"
        elif token in ("week", "weeks", "weekly"):
            period_tag = "week"
        elif token in ("month", "months", "monthly"):
            period_tag = "month"
        elif token in ("year", "years", "yearly"):
            period_tag = "year"

    numbers: list[float] = []
    for token in re.findall(r"[\d,]+(?:\.\d+)?\s*[kKmMbB]?", text):
        token = token.strip().replace(",", "")
        unit = 1.0
        if token[-1:].lower() == "k":
            unit = 1_000
            token = token[:-1].strip()
        elif token[-1:].lower() == "m":
            unit = 1_000_000
            token = token[:-1].strip()
        elif token[-1:].lower() == "b":
            unit = 1_000_000_000
            token = token[:-1].strip()
        try:
            numbers.append(float(token) * unit)
        except ValueError:
            continue

    if not numbers:
        return 0, 0, currency, period_tag

    min_v: int | None = int(numbers[0])
    max_v: int | None = int(numbers[-1]) if len(numbers) > 1 else None
    if "up to" in lower or "upto" in lower:
        min_v, max_v = 0, int(numbers[0])
    elif "from" in lower or "starting at" in lower:
        min_v = int(numbers[0])
        max_v = None
    return min_v, max_v, currency, period_tag


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
    if unit.startswith("minute"):
        delta = timedelta(minutes=amount)
    elif unit.startswith("hour"):
        delta = timedelta(hours=amount)
    elif unit.startswith("day"):
        delta = timedelta(days=amount)
    elif unit.startswith("week"):
        delta = timedelta(weeks=amount)
    elif unit.startswith("month"):
        delta = timedelta(days=amount * 30)
    elif unit.startswith("year"):
        delta = timedelta(days=amount * 365)
    else:
        return None
    return (datetime.now(UTC) - delta).isoformat()


def _parse_experience(text: str | None) -> int | None:
    if not text:
        return None
    m = _EXP_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _map_employment_type(text: str) -> str | None:
    if not text:
        return None
    lower = text.lower()
    if any(k in lower for k in ("full time", "full-time", "fulltime")):
        return "full_time"
    if any(k in lower for k in ("part time", "part-time", "parttime")):
        return "part_time"
    if any(k in lower for k in ("contract", "temporary")):
        return "contract"
    if any(k in lower for k in ("intern", "internship")):
        return "intern"
    return None


def _abs_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return urljoin(_BASE_URL, path)


def _clean_markdown_section(text: str) -> str:
    """Strip markdown link/bold syntax and collapse whitespace."""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _extract_benefit_items(lines: list[str]) -> list[str]:
    """Pull benefit labels out of a benefits section body."""
    items: list[str] = []
    for line in lines:
        m = re.match(r"^\s*\*\*([^*:]+)\*\*", line)
        if m:
            label = m.group(1).strip()
            if label and label not in items:
                items.append(label)
    return items


def _is_major_heading(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in _MAJOR_SECTION_KEYWORDS)


def _parse_detail_markdown(content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Parse Indeed detail markdown into normalized fields."""
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    heading_re = re.compile(r"^\s*(?:#{1,6}\s+|\*\*([^*]+?)\*\*)\s*$")

    for line in content.splitlines():
        match = heading_re.match(line)
        if match and _is_major_heading(match.group(1) or match.group(0)):
            if current_heading is not None or current_body:
                sections.append((current_heading, current_body))
            current_heading = (
                match.group(1).strip().rstrip(":")
                if match.group(1)
                else match.group(0).strip()
            )
            current_body = []
        else:
            current_body.append(line)
    if current_heading is not None or current_body:
        sections.append((current_heading, current_body))

    job_description = ""
    job_requirement = ""
    benefits: list[str] = []
    salary_raw = ""
    location: str | None = None
    employment_type: str | None = None
    experience_years: int | None = None

    for heading, body in sections:
        if heading is None:
            # Content before the first heading is usually a company overview.
            if not job_description:
                job_description = _clean_markdown_section("\n".join(body))
            continue

        h_lower = heading.lower()

        if any(
            k in h_lower
            for k in (
                "responsibilities",
                "about the job",
                "job description",
                "the role",
                "what you'll do",
            )
        ):
            job_description = _clean_markdown_section("\n".join(body))
        elif any(
            k in h_lower
            for k in (
                "qualifications",
                "requirements",
                "what you bring",
                "what you need",
                "what we're looking for",
            )
        ):
            job_requirement = _clean_markdown_section("\n".join(body))
        elif "some of your benefits" in h_lower or h_lower in ("benefits", "perks"):
            benefits = _extract_benefit_items(body)
        elif any(k in h_lower for k in ("compensation", "salary", "pay")):
            if body:
                salary_raw = "\n".join(body).strip()
        elif "location" in h_lower or "work location" in h_lower:
            location = _clean_markdown_section("\n".join(body))
        elif any(
            k in h_lower for k in ("employment type", "job type", "work schedule")
        ):
            employment_type = _map_employment_type(
                _clean_markdown_section("\n".join(body))
            )

    # If no explicit salary section, fall back to any line that looks like pay.
    if not salary_raw:
        for line in content.splitlines():
            if "$" in line and re.search(r"\d", line):
                salary_raw = re.sub(r"\s+", " ", line).strip()
                break

    # Strip the common equal-opportunity footer that bleeds into the last section.
    eeo_re = re.compile(
        r"\s*The\s+.+?\s+is\s+an\s+equal\s+opportunity\s+employer.*$",
        re.IGNORECASE,
    )
    job_description = eeo_re.sub("", job_description).strip()
    job_requirement = eeo_re.sub("", job_requirement).strip()

    if employment_type is None:
        employment_type = _map_employment_type(content)
    if experience_years is None:
        experience_years = _parse_experience(content)
    if location is None and metadata.get("description"):
        location = _map_location_from_text(metadata["description"])

    return {
        "job_description": job_description,
        "job_requirement": job_requirement,
        "benefits": benefits,
        "salary_raw": salary_raw or None,
        "employment_type": employment_type,
        "location": location,
        "experience_years": experience_years,
        "apply_url": None,
    }


def _map_location_from_text(text: str) -> str | None:
    """Pick the most likely location from a free-form description."""
    if not text:
        return None
    # City, ST or City, State patterns, plus common "in <City>" forms.
    m = re.search(r"(?:\bin\s+|\b)([A-Z][A-Za-z\s]+(?:,\s*[A-Z]{2})?)\b", text)
    if m:
        return m.group(1).strip()
    return None


def _parse_detail_html(html: str) -> dict[str, Any]:
    """Fallback HTML parser for Indeed detail pages."""
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return {}

    section_div = root.xpath('//div[@id="jobDescriptionText"]')
    if not section_div:
        section_div = root.xpath(
            '//div[contains(@class,"jobsearch-JobComponent-description")]'
        )
    if not section_div:
        return {}

    container = section_div[0]
    lines: list[str] = []
    for el in container.iter():
        if el.tag in ("h2", "h3", "h4", "b", "strong"):
            t = _safe_text(el)
            if t:
                lines.append(f"**{t}**")
        elif el.tag in ("p", "li"):
            t = _safe_text(el)
            if t:
                if el.tag == "li":
                    t = f"- {t}"
                lines.append(t)

    md = "\n".join(lines)
    return _parse_detail_markdown(md, {})


def _apply_detail(item: dict[str, Any], detail: dict[str, Any]) -> None:
    if detail.get("job_description"):
        item["job_description"] = detail["job_description"]
    if detail.get("job_requirement"):
        item["job_requirement"] = detail["job_requirement"]
    if detail.get("benefits"):
        item["benefits"] = detail["benefits"]
    if detail.get("location"):
        item["location"] = detail["location"]
    if detail.get("employment_type"):
        item["employment_type"] = detail["employment_type"]
    if detail.get("experience_years") is not None:
        item["experience_years"] = detail["experience_years"]

    salary_raw = detail.get("salary_raw") or item.get("salary_raw") or ""
    if salary_raw:
        item["salary_raw"] = salary_raw
        if any(
            k in salary_raw.lower()
            for k in ("negotiable", "competitive", "depends on experience", "doe")
        ):
            item["salary_min"] = 0
            item["salary_max"] = 0
            item["salary_currency"] = "USD"
            item["salary_period_id"] = "negotiable"
        else:
            min_v, max_v, currency, period = _extract_salary_numbers(salary_raw)
            item["salary_min"] = min_v
            item["salary_max"] = max_v
            item["salary_currency"] = currency
            item["salary_period_id"] = period

    if detail.get("apply_url"):
        item["source_url"] = detail["apply_url"]


def _parse_search_page(html: str) -> list[dict[str, Any]]:
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return []

    cards = root.xpath('//div[contains(@class,"job_seen_beacon")]')
    results: list[dict[str, Any]] = []

    for card in cards:
        title_link = card.xpath('.//h3[contains(@class,"jobTitle")]//a')
        if not title_link:
            continue

        a = title_link[0]
        jk = a.get("data-jk") or ""
        if not jk:
            href = a.get("href") or ""
            match = re.search(r"[?&]jk=([^&]+)", href)
            if match:
                jk = match.group(1)
        if not jk:
            continue

        title = ""
        title_spans = a.xpath(".//span/text()")
        if title_spans:
            title = " ".join(t.strip() for t in title_spans if t.strip())
        if not title:
            title = a.get("title") or ""
        if not title:
            title = a.get("aria-label") or ""
            title = re.sub(
                r"\bfull details of\s+", "", title, flags=re.IGNORECASE
            ).strip()

        company = ""
        company_els = card.xpath('.//span[@data-testid="company-name"]')
        if company_els:
            company = _safe_text(company_els[0]) or ""

        location = None
        loc_els = card.xpath('.//div[@data-testid="text-location"]')
        if loc_els:
            location = _safe_text(loc_els[0])

        summary_tags: list[str] = []
        for tag in card.xpath(
            './/div[contains(@class,"jobMetaDataGroup")]//span/text()'
        ):
            t = tag.strip()
            if t and len(t) > 1 and t not in summary_tags:
                summary_tags.append(t)

        salary_raw = ""
        salary_els = card.xpath(
            './/div[contains(@class,"salary-snippet")]//text()'
            ' | .//span[contains(@class,"estimated-salary")]//text()'
        )
        if salary_els:
            salary_raw = " ".join(t.strip() for t in salary_els if t.strip())

        posted = None
        posted_els = card.xpath(
            './/span[@data-testid="myJobsStateDate"]//text()'
            ' | .//span[contains(@class,"date")]//text()'
        )
        if posted_els:
            posted = _parse_posted(" ".join(t.strip() for t in posted_els if t.strip()))

        source_url = f"{_BASE_URL}/viewjob?jk={jk}"

        results.append(
            {
                "id": f"indeed:{jk}",
                "title": title,
                "company": company,
                "location": location,
                "source_url": source_url,
                "salary_raw": salary_raw,
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
                "salary_period_id": None,
                "employment_type": None,
                "experience_years": None,
                "job_description": "",
                "job_requirement": "",
                "benefits": summary_tags,
                "skills": [],
                "posted_at": posted,
                "is_active": True,
                "source": "indeed",
            }
        )

    return results


async def _fetch_search_page(
    keyword: str,
    location: str,
    radius: int,
    sort: str,
    start: int,
) -> str:
    # Local imports avoid an indeed <-> web_crawler circular import on startup.
    from app.proprietary.web_crawler.connector import scroll_to_bottom
    from app.proprietary.web_crawler.stealth import (
        build_stealthy_kwargs,
        get_stealth_config,
    )

    url = _search_url(keyword, location, radius, sort, start)
    kwargs: dict[str, Any] = {
        "headless": True,
        "network_idle": True,
        "block_ads": True,
        "solve_cloudflare": True,
        "proxy": None,
    }
    kwargs.update(build_stealthy_kwargs(get_stealth_config()))
    kwargs["page_action"] = scroll_to_bottom

    page = await asyncio.to_thread(StealthyFetcher.fetch, url, **kwargs)
    html = getattr(page, "html_content", "")
    if not html:
        raise ValueError("empty search page")
    return html


async def _fetch_detail_page(url: str) -> dict[str, Any]:
    from app.proprietary.web_crawler.connector import WebCrawlerConnector
    from app.proprietary.web_crawler.stealth import (
        build_stealthy_kwargs,
        get_stealth_config,
    )

    connector = WebCrawlerConnector()
    outcome = await connector.crawl_url(url)
    if outcome.status == "success" and outcome.result:
        content = outcome.result.get("content") or ""
        metadata = outcome.result.get("metadata") or {}
        if content:
            return _parse_detail_markdown(content, metadata)
        html = outcome.result.get("html") or ""
        if html:
            return _parse_detail_html(html)

    # Fallback to a raw browser fetch if the crawler produced no content.
    kwargs: dict[str, Any] = {
        "headless": True,
        "network_idle": True,
        "block_ads": True,
        "solve_cloudflare": True,
        "proxy": None,
    }
    kwargs.update(build_stealthy_kwargs(get_stealth_config()))

    page = await asyncio.to_thread(StealthyFetcher.fetch, url, **kwargs)
    html = getattr(page, "html_content", "")
    if not html:
        return {}
    return _parse_detail_html(html)


async def _scrape(params: dict[str, Any]) -> dict[str, Any]:
    max_items = int(params.get("max_items", config.INDEED_MAX_ITEMS) or 0)
    max_pages = int(params.get("max_pages", config.INDEED_MAX_PAGES) or 0)

    if max_items == 0 or max_pages == 0:
        return {
            "items": [],
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 0,
        }

    keyword = params.get("keyword", "data engineer")
    location = params.get("location", "") or ""
    radius = int(params.get("radius", 25) or 0)
    sort = params.get("sort", "relevance")
    items: list[dict[str, Any]] = []
    seen_jk: set[str] = set()
    cost_micros = 0
    start = 0

    try:
        for _ in range(max_pages):
            remaining = max(0, max_items - len(items))
            if remaining == 0:
                break

            html = await _fetch_search_page(keyword, location, radius, sort, start)

            cards = _parse_search_page(html)
            if not cards:
                break

            for card in cards[:remaining]:
                jk = card["id"]
                if jk in seen_jk:
                    continue
                seen_jk.add(jk)

                detail = await _fetch_detail_page(card["source_url"])
                _apply_detail(card, detail)
                cost_micros += config.INDEED_SCRAPE_MICROS_PER_ITEM
                items.append(card)

                if len(items) >= max_items:
                    break

                await asyncio.sleep(config.INDEED_PAGE_DELAY_S)

            if len(items) >= max_items:
                break

            start += len(cards)
            await asyncio.sleep(config.INDEED_PAGE_DELAY_S)

    except Exception as exc:
        logger.warning("indeed.scrape failed: %s", exc)
        if not items:
            return _degraded("anti_bot_block", cost_micros=cost_micros)

    if not items:
        return _degraded("anti_bot_block", cost_micros=cost_micros)

    return {
        "items": items,
        "cost_micros": cost_micros,
        "degraded": False,
        "degradation_reason": None,
        "total_items": len(items),
    }


async def scrape_indeed(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch and parse Indeed job search + detail pages."""
    try:
        return await _scrape(params)
    except TimeoutError:
        return _degraded("timeout")
    except Exception as exc:
        logger.warning("indeed.scrape failed: %s", exc)
        return _degraded("anti_bot_block")
