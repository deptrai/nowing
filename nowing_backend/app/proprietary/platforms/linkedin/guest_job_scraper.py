"""LinkedIn Public Guest Jobs API Scraper (Story 12.10 / AD-LI-1, AD-LI-2, AD-LI-5).

Ingests public job postings without login credentials using httpx + selectolax.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import unquote

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import LinkedinCompany, LinkedinJob
from app.proprietary.platforms.linkedin.schemas import LinkedInJobPosting

logger = logging.getLogger(__name__)

_GUEST_SEARCH_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_GUEST_DETAIL_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

_JOB_ID_REGEX = re.compile(r"(?:urn:li:jobPosting:|\/jobs\/view\/.*?-|currentJobId=)(\d{8,14})")
_COMPANY_SLUG_REGEX = re.compile(r"linkedin\.com\/company\/([a-zA-Z0-9\-_]+)", re.IGNORECASE)
_AGE_REGEX = re.compile(r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months)\s+ago", re.IGNORECASE)

_COMMON_SKILL_KEYWORDS = [
    "Python", "FastAPI", "Django", "Flask", "Go", "Golang", "Java", "Spring Boot",
    "C++", "C#", ".NET", "Rust", "Node.js", "TypeScript", "JavaScript", "React",
    "Next.js", "Vue", "Angular", "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis",
    "Elasticsearch", "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform",
    "CI/CD", "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow", "LLM",
    "NLP", "Data Engineering", "Spark", "Kafka", "Hadoop", "Airflow", "GraphQL",
    "REST API", "Microservices", "System Design", "Agile", "Scrum", "DevOps",
]


def _slugify(text: str) -> str:
    """Normalize text into clean URL slug."""
    text = unquote(text or "").lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text or "unknown"


def _parse_relative_age(text: str | None) -> datetime | None:
    """Parse relative age text (e.g. '5 days ago', '1 week ago') into datetime."""
    if not text:
        return None
    match = _AGE_REGEX.search(text.strip())
    if not match:
        return None
    count = int(match.group(1))
    unit = match.group(2).lower()
    now = datetime.now(UTC)

    if "minute" in unit:
        return now - timedelta(minutes=count)
    if "hour" in unit:
        return now - timedelta(hours=count)
    if "day" in unit:
        return now - timedelta(days=count)
    if "week" in unit:
        return now - timedelta(weeks=count)
    if "month" in unit:
        return now - timedelta(days=count * 30)
    return None


def _infer_workplace_type(location_text: str, title_text: str) -> str | None:
    """Infer workplace type (Remote, Hybrid, On-site) from strings."""
    combined = f"{location_text} {title_text}".lower()
    if "remote" in combined:
        return "Remote"
    if "hybrid" in combined:
        return "Hybrid"
    if "on-site" in combined or "onsite" in combined:
        return "On-site"
    return None


def parse_guest_job_cards(html_content: str) -> list[LinkedInJobPosting]:
    """Parse LinkedIn Guest Search HTML snippet into normalized LinkedInJobPosting objects."""
    if not html_content or not html_content.strip():
        return []

    tree = HTMLParser(html_content)
    jobs: list[LinkedInJobPosting] = []
    seen_ids: set[str] = set()

    # Cards are structured as li or div.base-card / div.job-search-card
    card_nodes = tree.css("li, div.base-card, div.job-search-card")

    for card in card_nodes:
        # 1. Job ID extraction
        entity_urn = card.attributes.get("data-entity-urn", "")
        card_id = card.attributes.get("data-id", "")
        link_node = card.css_first("a.base-card__full-link, a[href*='/jobs/view/']")
        link_href = link_node.attributes.get("href", "") if link_node else ""

        raw_id_candidate = f"{entity_urn} {card_id} {link_href}"
        m = _JOB_ID_REGEX.search(raw_id_candidate)
        if not m:
            continue
        job_id = m.group(1)
        if job_id in seen_ids:
            continue

        # 2. Title extraction
        title_node = card.css_first(".base-search-card__title, .sr-only, h3, h4")
        title = title_node.text().strip() if title_node else "Job Opportunity"

        # 3. Company extraction
        company_link = card.css_first("a[href*='linkedin.com/company/'], a.hidden-nested-link")
        company_subtitle = card.css_first(".base-search-card__subtitle")
        company_name = ""
        company_slug = ""

        if company_link:
            company_name = company_link.text().strip()
            slug_match = _COMPANY_SLUG_REGEX.search(company_link.attributes.get("href", ""))
            if slug_match:
                company_slug = slug_match.group(1).rstrip("/")
        if not company_name and company_subtitle:
            company_name = company_subtitle.text().strip()
        if not company_name:
            company_name = "Unknown Company"
        if not company_slug:
            company_slug = _slugify(company_name)

        # 4. Location extraction
        loc_node = card.css_first(".job-search-card__location, .base-search-card__metadata span")
        location = loc_node.text().strip() if loc_node else "Vietnam"

        # 5. Posted timestamp extraction
        time_node = card.css_first("time, .job-search-card__listdate")
        posted_at: datetime | None = None
        if time_node:
            dt_attr = time_node.attributes.get("datetime")
            if dt_attr:
                try:
                    posted_at = datetime.fromisoformat(dt_attr).replace(tzinfo=UTC)
                except Exception:
                    posted_at = _parse_relative_age(time_node.text())
            else:
                posted_at = _parse_relative_age(time_node.text())

        # 6. Workplace type
        workplace_type = _infer_workplace_type(location, title)

        # Clean source URL
        source_url = link_href.split("?")[0] if link_href else f"https://www.linkedin.com/jobs/view/{job_id}"

        job = LinkedInJobPosting(
            job_id=job_id,
            title=title,
            company_name=company_name,
            company_slug=company_slug,
            location=location,
            workplace_type=workplace_type,
            posted_at=posted_at,
            source_url=source_url,
            raw_entities={"card_html_tag": card.tag},
        )
        seen_ids.add(job_id)
        jobs.append(job)

    return jobs


def parse_guest_job_detail(html_content: str) -> dict[str, Any]:
    """Parse LinkedIn Guest Job Detail HTML page into rich description & criteria."""
    if not html_content or not html_content.strip():
        return {}

    tree = HTMLParser(html_content)

    title_node = tree.css_first(".top-card-layout__title, h1, h2")
    title = title_node.text().strip() if title_node else ""

    company_node = tree.css_first(".topcard__org-name-link, .topcard__flavor--black-link")
    company_name = company_node.text().strip() if company_node else ""

    desc_node = tree.css_first(".show-more-less-html__markup, .description__text, .decorated-job-posting__details")
    description_text = desc_node.text().strip() if desc_node else ""

    seniority_level: str | None = None
    employment_type: str | None = None

    criteria_items = tree.css(".description__job-criteria-item")
    for item in criteria_items:
        subheader = item.css_first(".description__job-criteria-subheader")
        text_node = item.css_first(".description__job-criteria-text")
        if not subheader or not text_node:
            continue
        header_text = subheader.text().strip().lower()
        val = text_node.text().strip()

        if "seniority" in header_text:
            seniority_level = val
        elif "employment" in header_text:
            employment_type = val

    # Extract skill tags
    skills: list[str] = []
    text_to_search = f"{title} {description_text}"
    for skill in _COMMON_SKILL_KEYWORDS:
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, text_to_search, re.IGNORECASE):
            skills.append(skill)

    return {
        "title": title,
        "company_name": company_name,
        "description_text": description_text,
        "seniority_level": seniority_level,
        "employment_type": employment_type,
        "skills": skills,
    }


class LinkedInGuestJobScraper:
    """Zero-login Public LinkedIn Job Scraper with residential proxy & human jitter (AD-LI-1, AD-LI-2)."""

    def __init__(
        self,
        proxy_url: str | None = None,
        timeout: float = 20.0,
        jitter_delay: tuple[float, float] = (1.5, 3.5),
    ) -> None:
        self.proxy_url = proxy_url or config.PROXY_URL
        self.timeout = timeout
        self.jitter_delay = jitter_delay

    def _get_headers(self) -> dict[str, str]:
        """Generate stealth headers mimicking modern browser requests."""
        return {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _fetch_url(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> str | None:
        """Fetch raw HTML with proxy and human jitter delay."""
        headers = self._get_headers()
        should_close = False

        if client is None:
            proxies = self.proxy_url if self.proxy_url else None
            client = httpx.AsyncClient(
                proxy=proxies,
                timeout=self.timeout,
                follow_redirects=True,
            )
            should_close = True

        try:
            # Human jitter rate limiting (AD-LI-2)
            if self.jitter_delay[1] > 0:
                await asyncio.sleep(random.uniform(self.jitter_delay[0], self.jitter_delay[1]))

            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 429:
                logger.warning("LinkedIn guest jobs endpoint rate limited (429)")
                return None
            if resp.status_code in (403, 451):
                logger.warning(f"LinkedIn guest jobs endpoint blocked ({resp.status_code})")
                return None
            if resp.status_code != 200:
                logger.warning(f"LinkedIn request failed with status {resp.status_code}")
                return None

            return resp.text
        except httpx.RequestError as exc:
            logger.error(f"HTTP request error querying LinkedIn jobs: {exc}")
            return None
        except Exception as exc:
            logger.exception(f"Unexpected error querying LinkedIn jobs: {exc}")
            return None
        finally:
            if should_close:
                await client.aclose()

    async def get_job_detail(
        self,
        job_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Fetch full description and criteria for a specific job ID."""
        url = f"{_GUEST_DETAIL_ENDPOINT}/{job_id}"
        html = await self._fetch_url(url, client=client)
        if not html:
            return {}
        return parse_guest_job_detail(html)

    async def search_jobs(
        self,
        keyword: str = "",
        location: str = "Vietnam",
        company_slug: str | None = None,
        limit: int = 25,
        fetch_details: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> list[LinkedInJobPosting]:
        """Search public guest jobs by keyword, location, or company slug."""
        all_jobs: list[LinkedInJobPosting] = []
        page_size = 25
        max_pages = (limit + page_size - 1) // page_size

        search_keyword = keyword
        if company_slug and not search_keyword:
            search_keyword = company_slug

        for page in range(max_pages):
            start = page * page_size
            params = {
                "keywords": search_keyword,
                "location": location,
                "start": str(start),
            }

            html = await self._fetch_url(_GUEST_SEARCH_ENDPOINT, params=params, client=client)
            if not html:
                break

            jobs = parse_guest_job_cards(html)
            if not jobs:
                break

            all_jobs.extend(jobs)
            if len(all_jobs) >= limit:
                break

        final_jobs = all_jobs[:limit]

        # Optional detail enrichment
        if fetch_details:
            for job in final_jobs:
                detail = await self.get_job_detail(job.job_id, client=client)
                if detail:
                    if detail.get("description_text"):
                        job.description_text = detail["description_text"]
                    if detail.get("seniority_level"):
                        job.seniority_level = detail["seniority_level"]
                    if detail.get("employment_type"):
                        job.employment_type = detail["employment_type"]
                    if detail.get("skills"):
                        job.skills = list(set(job.skills + detail["skills"]))

        return final_jobs


async def persist_linkedin_jobs(
    jobs: list[LinkedInJobPosting],
    session: AsyncSession,
) -> int:
    """Idempotently persist scraped jobs and companies to PostgreSQL (AD-LI-5)."""
    if not jobs:
        return 0

    persisted_count = 0
    now = datetime.now(UTC)

    # 1. Group jobs by company and upsert companies
    companies_dict: dict[str, str] = {}
    for job in jobs:
        slug = job.company_slug or _slugify(job.company_name)
        companies_dict[slug] = job.company_name

    company_id_map: dict[str, int] = {}

    for slug, name in companies_dict.items():
        stmt = (
            pg_insert(LinkedinCompany)
            .values(
                company_slug=slug,
                company_name=name,
                active_jobs_count=len([j for j in jobs if (j.company_slug == slug or _slugify(j.company_name) == slug)]),
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[LinkedinCompany.company_slug],
                set_={
                    "company_name": name,
                    "updated_at": now,
                },
            )
            .returning(LinkedinCompany.id, LinkedinCompany.company_slug)
        )
        result = await session.execute(stmt)
        row = result.fetchone()
        if row:
            company_id_map[row[1]] = row[0]

    # 2. Upsert jobs with foreign key linking
    for job in jobs:
        slug = job.company_slug or _slugify(job.company_name)
        comp_id = company_id_map.get(slug)

        job_stmt = (
            pg_insert(LinkedinJob)
            .values(
                job_id=job.job_id,
                company_id=comp_id,
                company_name=job.company_name,
                title=job.title,
                location=job.location,
                workplace_type=job.workplace_type,
                seniority_level=job.seniority_level,
                employment_type=job.employment_type,
                description_text=job.description_text,
                skills=job.skills,
                posted_at=job.posted_at or now,
                raw_entities=job.raw_entities,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[LinkedinJob.job_id],
                set_={
                    "title": job.title,
                    "location": job.location,
                    "description_text": job.description_text,
                    "skills": job.skills,
                    "updated_at": now,
                },
            )
        )
        await session.execute(job_stmt)
        persisted_count += 1

    await session.commit()
    return persisted_count
