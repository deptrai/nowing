"""TopCV HTML fetcher with anti-bot handling."""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from lxml import html as lxml_html
from scrapling.fetchers import StealthyFetcher

from app.config import config
from app.utils.crawl import BlockType, classify_block

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.topcv.vn"

# Circuit-breaker state (module-level; thread-safe because asyncio is single-threaded).
_consecutive_failures = 0
_circuit_open_until = 0.0

_SALARY_PERIOD_RE = re.compile(r"\b(tháng|month|năm|year|giờ|hour|ngày|day)\b", re.IGNORECASE)
_SALARY_NUMBER_RE = re.compile(r"[\d\.,]+\s*(?:tr(?:iệu)?|k|m|b|t)?", re.IGNORECASE)
_AGE_RE = re.compile(
    r"(?:đăng\s+)?(\d+)\s+(phút|giờ|ngày|tuần|tháng|năm)\s+trước",
    re.IGNORECASE,
)
_NEGOTIATION_KEYWORDS = ("thoả thuận", "thương lượng", "negotiable", "thỏa thuận")


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
    """Convert a Vietnamese search phrase into a TopCV URL slug."""
    text = re.sub(r"[^a-z0-9\s+-]", "", value.lower())
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    slug = text.strip("-")
    if not slug:
        return "viec-lam"
    # ponytail: `+` is a valid path sub-delimiter; `#` is the fragment character
    # and is stripped above rather than percent-encoded.
    return quote(slug, safe="/+-")


def _topcv_search_url(keyword: str, page: int) -> str:
    slug = _normalize_keyword(keyword)
    url = f"{_BASE_URL}/tim-viec-lam-{slug}"
    if page > 1:
        url = f"{url}?page={page}"
    return url


def _clean_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{parsed.netloc}{parsed.path}{query}"


def _extract_salary_numbers(
    text: str,
) -> tuple[int | None, int | None, str, str | None, bool, str]:
    """Return (min, max, currency, period, salary_hidden, salary_confidence)."""
    if not text:
        return 0, 0, "VND", "month", True, "low"

    lower = text.lower()
    if any(k in lower for k in _NEGOTIATION_KEYWORDS):
        return 0, 0, "VND", "negotiable", True, "low"

    currency = "USD" if "$" in text or "usd" in lower else "VND"

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

    numbers: list[float] = []
    units: list[float] = []
    for raw_token in re.findall(_SALARY_NUMBER_RE, text):
        token = raw_token.strip()
        if not token:
            continue

        # Vietnamese: dot = thousands, comma = decimal. English: comma = thousands, dot = decimal.
        if currency == "VND":
            token = re.sub(r"\.(?=\d{3}(?:\D|$))", "", token).replace(",", ".")
        else:
            token = token.replace(",", "")

        lower_token = token.lower()
        unit = 1.0
        if lower_token.endswith("tr") or lower_token.endswith("triệu") or lower_token.endswith("m"):
            unit = 1_000_000
            token = re.sub(r"(?i)(tr(?:iệu)?|m)$", "", token).strip()
        elif lower_token.endswith("k"):
            unit = 1_000
            token = token[:-1].strip()
        elif lower_token.endswith("b"):
            unit = 1_000_000_000
            token = token[:-1].strip()
        elif lower_token.endswith("t"):
            unit = 1_000_000_000_000
            token = token[:-1].strip()

        try:
            numbers.append(float(token))
            units.append(unit)
        except ValueError:
            continue

    if not numbers:
        return 0, 0, currency, period_tag or "month", True, "low"

    # Normalize unit-less numbers to the shared magnitude found elsewhere in the text.
    shared_unit = next((u for u in units if u > 1), 1.0)
    if shared_unit > 1:
        numbers = [n * (shared_unit if u == 1 else u) for n, u in zip(numbers, units, strict=True)]
    else:
        numbers = [n * u for n, u in zip(numbers, units, strict=True)]

    min_v: int | None = int(numbers[0])
    max_v: int | None = int(numbers[-1]) if len(numbers) > 1 else None
    has_from = "từ" in lower or "from" in lower
    has_to = "tới" in lower or "up to" in lower or "đến" in lower
    if has_from and has_to:
        min_v, max_v = int(numbers[0]), int(numbers[-1]) if len(numbers) > 1 else int(numbers[0])
    elif has_to:
        min_v, max_v = 0, int(numbers[0])
    elif has_from:
        min_v = int(numbers[0])
        max_v = int(numbers[-1]) if len(numbers) > 1 else None
    return min_v, max_v, currency, period_tag or "month", False, "medium"


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
    if unit in ("phút",):
        delta = timedelta(minutes=amount)
    elif unit in ("giờ",):
        delta = timedelta(hours=amount)
    elif unit in ("ngày",):
        delta = timedelta(days=amount)
    elif unit in ("tuần",):
        delta = timedelta(weeks=amount)
    elif unit in ("tháng",):
        delta = timedelta(days=amount * 30)
    elif unit in ("năm",):
        delta = timedelta(days=amount * 365)
    else:
        return None
    return (datetime.now(UTC) - delta).isoformat()


def _parse_experience(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)\s*\+?\s*(?:năm|years?)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _is_requirement_tag(text: str) -> bool:
    """Filter out experience/education tags masquerading as skills."""
    if not text:
        return True
    lower = text.lower()
    return any(
        k in lower
        for k in (
            "năm",
            "year",
            "kinh nghiệm",
            "trở lên",
            "cao đẳng",
            "đại học",
            "trung cấp",
            "...",
        )
    )


def _map_employment_type(text: str) -> str | None:
    if not text:
        return None
    lower = text.lower()
    if any(k in lower for k in ("toàn thời gian", "full time", "full-time")):
        return "full_time"
    if any(k in lower for k in ("bán thời gian", "part time", "part-time")):
        return "part_time"
    if any(k in lower for k in ("thực tập", "intern")):
        return "intern"
    if "hợp đồng" in lower or "contract" in lower:
        return "contract"
    return None


def _abs_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return urljoin(_BASE_URL, path)


def _parse_detail_markdown(content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Parse TopCV detail markdown into normalized fields."""
    # Sections are delimited by ## headings in Vietnamese.
    sections: dict[str, str] = {}
    current_heading = None
    current_body: list[str] = []

    for line in content.splitlines():
        heading_match = re.match(r"^##\s+(.+)$", line.strip())
        if heading_match:
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_body).strip()
            current_heading = heading_match.group(1).strip()
            current_body = []
        elif current_heading is not None:
            current_body.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(current_body).strip()

    jd = _clean_markdown_section(sections.get("Mô tả công việc", ""))
    req = _clean_markdown_section(sections.get("Yêu cầu ứng viên", ""))

    location_section = sections.get("Địa điểm và thời gian", "")
    location = None
    if location_section:
        # TopCV renders the location as "**City:** street address" inside the
        # "Địa điểm làm việc" subsection. Stop at the next ###/## heading.
        m = re.search(
            r"\*\*([^*]+):\*\*\s*(.+?)(?=\n###|\n##|$)",
            location_section,
            re.DOTALL,
        )
        if m:
            city = m.group(1).strip()
            address = re.sub(r"\s+", " ", m.group(2)).strip()
            address = re.sub(r"###\s*.*", "", address).strip()
            location = f"{city}: {address}" if address else city

    # Employment type from the schedule section if available.
    employment_type = None
    schedule_section = sections.get("Thời gian làm việc", "")
    if schedule_section:
        employment_type = _map_employment_type(schedule_section)

    # Skills / experience / salary / employment type from the meta description.
    description = metadata.get("description", "") or ""
    skills: list[str] = []
    experience_years = None
    salary_raw = ""

    skill_match = re.search(r"kỹ\s+năng\s+(.+)", description, re.IGNORECASE)
    if skill_match:
        skills = [s.strip() for s in skill_match.group(1).split(",") if s.strip()]
    exp_match = re.search(r"kinh\s+nghiệm\s+(\d+)\s*năm", description, re.IGNORECASE)
    if exp_match:
        experience_years = int(exp_match.group(1))
    salary_match = re.search(r"lương\s+([^,]+)", description, re.IGNORECASE)
    if salary_match:
        salary_raw = salary_match.group(1).strip()
    if not employment_type:
        employment_type = _map_employment_type(description) or _map_employment_type(content)

    return {
        "job_description": jd,
        "job_requirement": req,
        "location": location,
        "employment_type": employment_type,
        "skills": skills,
        "experience_years": experience_years,
        "salary_raw": salary_raw or None,
    }


def _clean_markdown_section(text: str) -> str:
    """Strip markdown link syntax and collapse whitespace."""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*|\*", " ", text)
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_search_page(html: str) -> list[dict[str, Any]]:
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return []

    cards = root.xpath('//div[contains(@class,"job-item-search-result")]')
    results: list[dict[str, Any]] = []

    for card in cards:
        job_id = card.get("data-job-id", "")

        title = ""
        title_link = card.xpath('.//h3[contains(@class,"title")]//a/@href')
        title_el = card.xpath('.//h3[contains(@class,"title")]//a//span[@data-toggle="tooltip"]')
        if title_el:
            title = _safe_text(title_el[0]) or ""
        if not title:
            title_el = card.xpath('.//h3[contains(@class,"title")]//a')[0:1]
            if title_el:
                title = _safe_text(title_el[0]) or ""

        source_url = ""
        if title_link:
            source_url = _clean_url(_abs_url(title_link[0]))

        company = ""
        company_el = card.xpath('.//a[contains(@class,"company")]//span[contains(@class,"company-name")]')
        if company_el:
            company = _safe_text(company_el[0]) or ""

        location = None
        city_el = card.xpath('.//label[contains(@class,"address")]//span[contains(@class,"city-text")]')
        if city_el:
            location = _safe_text(city_el[0])

        salary_raw = ""
        salary_els = card.xpath('.//label[contains(@class,"salary")]//span') or card.xpath('.//label[contains(@class,"title-salary")]')
        if salary_els:
            salary_raw = _safe_text(salary_els[0]) or ""

        min_v, max_v, currency, period, salary_hidden, salary_confidence = _extract_salary_numbers(salary_raw)

        experience = None
        exp_els = card.xpath('.//label[contains(@class,"exp")]//span')
        if exp_els:
            experience = _parse_experience(_safe_text(exp_els[0]) or "")

        posted = None
        posted_els = card.xpath('.//label[contains(@class,"label-update")]')
        if posted_els:
            posted = _parse_posted(_safe_text(posted_els[0])) or _parse_posted(
                posted_els[0].get("data-original-title") or ""
            )

        tags: list[str] = []
        tag_container = card.xpath('.//div[@class="tag"]')
        if tag_container:
            for tag in tag_container[0].xpath(
                './/a[contains(@class,"item-tag")] | .//span[contains(@class,"item-tag")]'
            ):
                tag_text = _safe_text(tag)
                if tag_text and not tag_text.startswith("+") and not _is_requirement_tag(tag_text) and tag_text not in tags:
                    tags.append(tag_text)
            for remaining in tag_container[0].xpath('.//span[contains(@class,"remaining-items")]'):
                tooltip = remaining.get("data-original-title") or ""
                for part in tooltip.split(","):
                    part = part.strip()
                    if part and not _is_requirement_tag(part) and part not in tags:
                        tags.append(part)

        results.append({
            "id": f"topcv:{job_id}",
            "title": title,
            "company": company,
            "location": location,
            "source_url": source_url,
            "salary_raw": salary_raw,
            "salary_min": min_v,
            "salary_max": max_v,
            "salary_currency": currency,
            "salary_period_id": period,
            "salary_hidden": salary_hidden,
            "salary_confidence": salary_confidence,
            "employment_type": None,
            "experience_years": experience,
            "job_description": "",
            "job_requirement": "",
            "skills": tags,
            "posted_at": posted,
            "is_active": True,
            "source": "topcv",
        })

    return results


def _apply_detail(item: dict[str, Any], detail: dict[str, Any]) -> None:
    if detail.get("job_description"):
        item["job_description"] = detail["job_description"]
    if detail.get("job_requirement"):
        item["job_requirement"] = detail["job_requirement"]
    if detail.get("location"):
        item["location"] = detail["location"]
    if detail.get("employment_type"):
        item["employment_type"] = detail["employment_type"]
    if detail.get("skills"):
        item["skills"] = detail["skills"]
    if detail.get("experience_years") is not None:
        item["experience_years"] = detail["experience_years"]

    salary_raw = detail.get("salary_raw") or item.get("salary_raw") or ""
    if salary_raw:
        item["salary_raw"] = salary_raw
    (
        item["salary_min"],
        item["salary_max"],
        item["salary_currency"],
        item["salary_period_id"],
        item["salary_hidden"],
        item["salary_confidence"],
    ) = _extract_salary_numbers(salary_raw)


def _degradation_reason_from_exception(exc: BaseException) -> str:
    msg = str(exc).lower()
    if "rate" in msg or "circuit open" in msg or "429" in msg:
        return "rate_limited"
    if isinstance(exc, TimeoutError):
        return "timeout"
    return "bot_detected"


def _looks_like_rate_limit(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "rate" in msg or "429" in msg or "circuit open" in msg


def _record_failure() -> None:
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures += 1
    if _consecutive_failures >= config.TOPCV_CIRCUIT_BREAKER_THRESHOLD:
        _circuit_open_until = time.monotonic() + config.TOPCV_CIRCUIT_BREAKER_TIMEOUT_S


def _user_agent_for_attempt(attempt: int) -> str | None:
    """Return a rotated User-Agent for retry attempts."""
    uas: list[str] = []
    if config.VIETNAMWORKS_USER_AGENT:
        uas.append(config.VIETNAMWORKS_USER_AGENT)
    uas.append(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )
    if not uas:
        return None
    return uas[(attempt - 1) % len(uas)]


def _backoff_seconds(attempt: int) -> float:
    return min(config.TOPCV_RETRY_BACKOFF_BASE_S * (2 ** attempt), 30.0) + random.uniform(0, 0.5)


def _validate_search_page(page: Any) -> None:
    """Raise a descriptive ValueError if the search page is blocked or empty."""
    html = getattr(page, "html_content", "") or ""
    status = getattr(page, "status", 0) or 0

    if not html.strip():
        raise ValueError("empty search page")

    if status == 429:
        raise ValueError("rate limited")
    if status == 403:
        raise ValueError("anti-bot challenge")
    if status >= 400:
        raise ValueError(f"search page error: status={status}")

    title = ""
    title_nodes = page.css("title")
    if title_nodes and title_nodes[0].text:
        title = str(title_nodes[0].text)
    if "just a moment..." in title.lower():
        raise ValueError("anti-bot challenge")

    block = classify_block(status, html)
    if block == BlockType.RATE_LIMITED:
        raise ValueError("rate limited")
    if block != BlockType.OK:
        raise ValueError("anti-bot challenge")


async def _fetch_search_page(keyword: str, page: int) -> str:
    # Local imports avoid a topcv <-> web_crawler circular import on startup.
    from app.proprietary.web_crawler.stealth import build_stealthy_kwargs, get_stealth_config  # noqa: I001
    from app.proprietary.web_crawler.connector import scroll_to_bottom

    if _circuit_open_until > time.monotonic():
        raise ValueError("circuit open")

    url = _topcv_search_url(keyword, page)
    base_kwargs: dict[str, Any] = {
        "headless": True,
        "network_idle": True,
        "block_ads": True,
        "solve_cloudflare": True,
        "proxy": None,
        "timeout": int(config.TOPCV_TIMEOUT_S * 1000),
    }
    base_kwargs.update(build_stealthy_kwargs(get_stealth_config()))
    base_kwargs["page_action"] = scroll_to_bottom

    attempts = max(0, config.TOPCV_RETRY_ATTEMPTS)
    last_exc: BaseException | None = None

    for attempt in range(attempts + 1):
        kwargs = dict(base_kwargs)
        if attempt > 0:
            ua = _user_agent_for_attempt(attempt)
            if ua:
                # ponytail: Scrapling accepts a `useragent` string; extra headers
                # are not needed here. If the fetcher is refactored to a connector,
                # UA rotation must move to the connector kwargs.
                kwargs["useragent"] = ua

        try:
            page_obj = await asyncio.wait_for(
                asyncio.to_thread(StealthyFetcher.fetch, url, **kwargs),
                timeout=config.TOPCV_TIMEOUT_S,
            )
            _validate_search_page(page_obj)
            global _consecutive_failures
            _consecutive_failures = 0
            return page_obj.html_content
        except Exception as exc:
            last_exc = exc
            if attempt == attempts:
                _record_failure()
                if _looks_like_rate_limit(exc):
                    raise ValueError("rate_limited") from exc
                raise
            await asyncio.sleep(_backoff_seconds(attempt))

    # Defensive fallback; the loop always either returns or raises.
    raise last_exc or ValueError("search page failed")


async def _fetch_detail_page(url: str) -> dict[str, Any]:
    from app.proprietary.web_crawler.connector import WebCrawlerConnector

    if _circuit_open_until > time.monotonic():
        raise ValueError("rate_limited")

    connector = WebCrawlerConnector()
    attempts = max(0, config.TOPCV_RETRY_ATTEMPTS)

    for attempt in range(attempts + 1):
        try:
            outcome = await asyncio.wait_for(
                connector.crawl_url(url),
                timeout=config.TOPCV_TIMEOUT_S,
            )
            if outcome.status == "success" and outcome.result:
                global _consecutive_failures
                _consecutive_failures = 0
                content = outcome.result.get("content") or ""
                metadata = outcome.result.get("metadata") or {}
                return _parse_detail_markdown(content, metadata)

            # Non-success outcome: classify and decide whether to retry or give up.
            if outcome.block_type == BlockType.RATE_LIMITED:
                raise ValueError("rate limited")
            if outcome.block_type not in (BlockType.OK, BlockType.UNKNOWN):
                raise ValueError("anti-bot challenge")
            if attempt == attempts:
                # ponytail: detail fetch returned empty/failed after all retries;
                # return an empty dict so the scrape loop can continue with the
                # search-card data rather than aborting the whole run.
                _record_failure()
                return {}
            raise ValueError("detail fetch failed")
        except Exception as exc:
            if attempt == attempts:
                _record_failure()
                if _looks_like_rate_limit(exc):
                    raise ValueError("rate_limited") from exc
                # Non-rate-limit detail failures are swallowed after retries.
                return {}
            await asyncio.sleep(_backoff_seconds(attempt))

    return {}


async def _scrape(params: dict[str, Any]) -> dict[str, Any]:
    if not config.TOPCV_ENABLED:
        return _degraded("legal_blocked")

    max_items = max(0, int(params.get("max_items", 50) or 0))
    max_pages = min(
        max(0, int(params.get("max_pages", 1) or 0)),
        config.TOPCV_MAX_PAGES,
    )
    start_page = max(1, int(params.get("page", 1) or 1))

    if max_items == 0 or max_pages == 0:
        return {
            "items": [],
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 0,
        }

    keyword = str(params.get("keyword", "viec-lam") or "").strip()
    if not keyword:
        logger.warning("topcv.scrape received empty keyword; defaulting to 'viec-lam'")
        keyword = "viec-lam"

    items: list[dict[str, Any]] = []
    cost_micros = 0

    try:
        end_page = start_page + max_pages - 1
        for page in range(start_page, end_page + 1):
            remaining = max(0, max_items - len(items))
            if remaining == 0:
                break

            html = await _fetch_search_page(keyword, page)
            cards = _parse_search_page(html)
            if not cards:
                break

            # Charge the heavier search fetch only after cards are successfully parsed.
            cost_micros += config.TOPCV_SCRAPE_MICROS_PER_ITEM * 3

            for card in cards[:remaining]:
                detail = await _fetch_detail_page(card["source_url"])
                if detail:
                    _apply_detail(card, detail)
                    cost_micros += config.TOPCV_SCRAPE_MICROS_PER_ITEM
                items.append(card)

                if len(items) >= max_items:
                    break

                await asyncio.sleep(config.TOPCV_PAGE_DELAY_S)

            if len(items) >= max_items:
                break
            await asyncio.sleep(config.TOPCV_PAGE_DELAY_S)

    except Exception as exc:
        logger.warning("topcv.scrape failed: %s", exc)
        reason = _degradation_reason_from_exception(exc)
        if not items:
            return _degraded(reason, cost_micros=cost_micros)
        return {
            "items": items,
            "cost_micros": cost_micros,
            "degraded": True,
            "degradation_reason": reason,
            "total_items": len(items),
        }

    return {
        "items": items,
        "cost_micros": cost_micros,
        "degraded": False,
        "degradation_reason": None,
        "total_items": len(items),
    }


async def scrape_topcv(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch and parse TopCV job search + detail pages."""
    if not config.TOPCV_ENABLED:
        return _degraded("legal_blocked")
    try:
        return await _scrape(params)
    except TimeoutError:
        return _degraded("timeout")
    except Exception as exc:
        logger.warning("topcv.scrape failed: %s", exc)
        return _degraded("bot_detected")
