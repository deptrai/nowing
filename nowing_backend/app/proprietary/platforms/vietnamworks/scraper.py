"""VietnamWorks public API fetcher."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger(__name__)

_API_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"

_TYPE_WORKING_MAP = {
    1: "full_time",
    2: "part_time",
    3: "contract",
    4: "intern",
}


def _degraded(reason: str) -> dict[str, Any]:
    return {
        "items": [],
        "cost_micros": 0,
        "degraded": True,
        "degradation_reason": reason,
        "total_items": 0,
    }


def _first_location(locations: list[dict[str, Any]]) -> str | None:
    if not locations:
        return None
    loc = locations[0]
    return loc.get("cityNameVI") or loc.get("cityName") or loc.get("address") or None


def _parse_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, int) and value > 0:
        # VietnamWorks sometimes returns Unix timestamps in milliseconds.
        from datetime import UTC, datetime

        ts_s = value / 1000 if value > 1e10 else value
        return datetime.fromtimestamp(ts_s, tz=UTC).isoformat()
    return None


def _normalize_salary(min_val: Any, max_val: Any, raw: str | None) -> tuple[int | None, int | None]:
    """Return (salary_min, salary_max).

    - 0/0 means negotiable -> keep both as 0.
    - min > 0, max == 0 means "From X" -> max is None.
    - min > 0, max > 0 means range -> keep both.
    """
    min_v = int(min_val) if min_val is not None else 0
    max_v = int(max_val) if max_val is not None else 0

    if min_v == 0 and max_v == 0:
        return 0, 0
    if min_v > 0 and max_v == 0:
        return min_v, None
    return min_v, max_v


def _normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise ValueError("job entry is not a dict")
    job_id = job.get("jobId")
    if job_id is None:
        raise ValueError("missing jobId in job entry")
    working_locations = job.get("workingLocations") or []
    salary_min, salary_max = _normalize_salary(
        job.get("salaryMin"), job.get("salaryMax"), job.get("prettySalary")
    )

    type_working_id = job.get("typeWorkingId")
    employment_type = _TYPE_WORKING_MAP.get(type_working_id) if type_working_id is not None else None

    skills = []
    for skill in job.get("skills") or []:
        name = skill.get("skillName") if isinstance(skill, dict) else None
        if name:
            skills.append(name)

    benefits = job.get("benefits") or []
    if not isinstance(benefits, list):
        benefits = []

    return {
        "id": f"vw:{job_id}" if job_id is not None else "vw:unknown",
        "title": job.get("jobTitle", ""),
        "company": job.get("companyName", ""),
        "location": _first_location(working_locations),
        "source_url": job.get("jobUrl", ""),
        "salary_raw": job.get("prettySalary", ""),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": job.get("salaryCurrency") or None,
        "salary_period_id": job.get("salaryPeriodId"),
        "employment_type": employment_type,
        "experience_years": job.get("yearsOfExperience"),
        "job_description": job.get("jobDescription", ""),
        "job_requirement": job.get("jobRequirement", ""),
        "job_function": job.get("jobFunction") or None,
        "skills": skills,
        "benefits": benefits,
        "posted_at": _parse_date(job.get("createdOn")),
        "approved_at": _parse_date(job.get("approvedOn")),
        "expired_at": _parse_date(job.get("expiredOn")),
        "is_active": bool(job.get("isActive", True)),
        "source": "vietnamworks",
    }


def _build_request_body(params: dict[str, Any], page: int, hits_per_page: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "keyword": params.get("keyword", ""),
        "page": page,
        "hitsPerPage": hits_per_page,
    }

    location_id = params.get("locationId")
    if location_id is not None:
        body["locationId"] = location_id

    salary_min = params.get("salary_min")
    if salary_min is not None:
        body["salaryMin"] = salary_min

    salary_max = params.get("salary_max")
    if salary_max is not None:
        body["salaryMax"] = salary_max

    experience_years = params.get("experience_years")
    if experience_years is not None:
        body["yearsOfExperience"] = experience_years

    employment_type = params.get("employment_type")
    if employment_type == "full_time":
        body["typeWorkingId"] = 1
    elif employment_type == "part_time":
        body["typeWorkingId"] = 2
    elif employment_type == "contract":
        body["typeWorkingId"] = 3
    elif employment_type == "intern":
        body["typeWorkingId"] = 4

    return body


def _extract_items(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    if "data" not in envelope:
        raise ValueError("missing 'data' field in response envelope")
    data = envelope["data"]
    if not isinstance(data, list):
        raise ValueError("'data' field is not a list")
    return [_normalize_job(job) for job in data]


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }


async def _do_request(client: httpx.AsyncClient, body: dict[str, Any]) -> httpx.Response:
    return await client.post(_API_URL, json=body, headers=_headers(), timeout=config.VIETNAMWORKS_TIMEOUT_S)


async def _scrape(params: dict[str, Any]) -> dict[str, Any]:
    max_items = int(params.get("max_items", 50) or 0)
    starting_page = int(params.get("page", 1) or 1)
    # If the caller explicitly passes a page, default to fetching just that page.
    default_max_pages = 1 if "page" in params else config.VIETNAMWORKS_MAX_PAGES
    max_pages = int(params.get("max_pages", default_max_pages) or 1)
    hits_per_page = min(int(params.get("hitsPerPage", 100) or 100), config.VIETNAMWORKS_MAX_ITEMS)

    if max_items == 0 or max_pages == 0:
        return {"items": [], "cost_micros": 0, "degraded": False, "degradation_reason": None}

    items: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for page in range(starting_page, starting_page + max_pages):
            # Limit the page size so we don't over-fetch on the last page.
            remaining = max(0, max_items - len(items))
            if remaining == 0:
                break
            page_size = min(hits_per_page, remaining)

            body = _build_request_body(params, page, page_size)
            resp = await _do_request(client, body)

            if resp.status_code == 429:
                return _degraded("rate_limited")
            if resp.status_code in (403, 451):
                return _degraded("access_blocked")
            if resp.status_code >= 500:
                return _degraded("api_error")
            resp.raise_for_status()

            try:
                envelope = resp.json()
            except Exception:
                return _degraded("decode_error")

            if not isinstance(envelope, dict):
                return _degraded("decode_error")

            page_items = _extract_items(envelope)
            if not page_items:
                break

            items.extend(page_items)

            meta = envelope.get("meta") or {}
            nb_pages = meta.get("nbPages")
            if nb_pages is not None and page >= int(nb_pages):
                break

            if len(items) >= max_items:
                break

            await asyncio.sleep(config.VIETNAMWORKS_PAGE_DELAY_S)

    # Clamp to max_items if the API returned more than requested.
    items = items[:max_items]

    return {
        "items": items,
        "cost_micros": 0,
        "degraded": False,
        "degradation_reason": None,
        "total_items": len(items),
    }


async def scrape_vietnamworks(params: dict[str, Any]) -> dict[str, Any]:
    """Call VietnamWorks ``POST /job-search/v1.0/search`` and return normalized items."""
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
    except ValueError as exc:
        logger.warning("vietnamworks response schema drift: %s", exc)
        return _degraded("schema_drift")
    except Exception as exc:
        logger.warning("vietnamworks.scrape failed: %s", exc)
        return _degraded("api_error")
