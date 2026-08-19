"""VietnamWorks public API fetcher."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
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


def _degraded(reason: str, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return a degraded response, preserving any items already collected."""
    final_items = items if items is not None else []
    return {
        "items": final_items,
        "cost_micros": 0,
        "degraded": True,
        "degradation_reason": reason,
        "total_items": len(final_items),
    }


def _first_location(locations: list[dict[str, Any]]) -> str | None:
    if not locations:
        return None
    loc = locations[0]
    return loc.get("cityNameVI") or loc.get("cityName") or loc.get("address") or None


def _parse_date(value: Any) -> str | None:
    """Parse VietnamWorks date values into an ISO-8601 date string.

    Accepts ISO strings (with or without time), Unix timestamps in seconds or
    milliseconds, and numeric/float/string numeric values. Returns ``None`` for
    empty or unparseable input.
    """
    if value is None or value == "":
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts <= 0:
            return None
        # Values larger than 1e12 are unambiguously milliseconds (year ~33688).
        ts_s = ts / 1000 if ts > 1e12 else ts
        return datetime.fromtimestamp(ts_s, tz=UTC).date().isoformat()

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Try full ISO first; if it has a time component, drop back to date.
        try:
            dt = datetime.fromisoformat(text)
            return dt.date().isoformat()
        except ValueError:
            pass
        # Fallback to date-only ISO.
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
        # Numeric timestamp passed as a string.
        try:
            ts = float(text)
            if ts <= 0:
                return None
            ts_s = ts / 1000 if ts > 1e12 else ts
            return datetime.fromtimestamp(ts_s, tz=UTC).date().isoformat()
        except ValueError:
            return None

    return None


def _to_int(value: Any) -> int | None:
    """Coerce a salary-ish value to an int, tolerating formatted strings."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        # Remove thousands separators (commas are unambiguous thousands).
        cleaned = text.replace(",", "")

        # If there is exactly one dot, try parsing as a decimal float first.
        # This handles "25.5" correctly as 25, not 255.
        if cleaned.count(".") == 1:
            try:
                return int(float(cleaned))
            except ValueError:
                pass

        # Otherwise treat any remaining dots as thousands separators.
        try:
            return int(cleaned.replace(".", ""))
        except ValueError:
            return None
    return None


def _normalize_salary(min_val: Any, max_val: Any) -> tuple[int | None, int | None]:
    """Return (salary_min, salary_max).

    - 0/0 means negotiable -> keep both as 0.
    - min > 0, max == 0 means "From X" -> max is None.
    - min == 0, max > 0 means "Up to X" -> min is None.
    - min > 0, max > 0 means range -> keep both.
    """
    min_v = _to_int(min_val)
    max_v = _to_int(max_val)

    if min_v is None and max_v is None:
        return 0, 0
    if min_v is None:
        min_v = 0
    if max_v is None:
        max_v = 0

    if min_v == 0 and max_v == 0:
        return 0, 0
    if min_v > 0 and max_v == 0:
        return min_v, None
    if min_v == 0 and max_v > 0:
        return None, max_v
    return min_v, max_v


def _normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise ValueError("job entry is not a dict")
    job_id = job.get("jobId")
    if job_id is None:
        raise ValueError("missing jobId in job entry")

    title = str(job.get("jobTitle", "")).strip()
    company = str(job.get("companyName", "")).strip()
    if not title or not company:
        raise ValueError("missing jobTitle or companyName in job entry")

    working_locations = job.get("workingLocations") or []
    salary_min, salary_max = _normalize_salary(
        job.get("salaryMin"), job.get("salaryMax")
    )

    type_working_id = job.get("typeWorkingId")
    employment_type = (
        _TYPE_WORKING_MAP.get(type_working_id) if type_working_id is not None else None
    )

    skills = []
    for skill in job.get("skills") or []:
        name = skill.get("skillName") if isinstance(skill, dict) else None
        if name:
            skills.append(name)

    benefits = job.get("benefits") or []
    if not isinstance(benefits, list):
        benefits = []

    is_active = job.get("isActive")
    # A missing or null isActive field does not mean the posting is inactive.
    is_active = is_active is None or is_active is True

    return {
        "id": f"vw:{job_id}",
        "title": str(job.get("jobTitle", "")).strip(),
        "company": str(job.get("companyName", "")).strip(),
        "location": _first_location(working_locations),
        "source_url": str(job.get("jobUrl", "")).strip(),
        "salary_raw": str(job.get("prettySalary", "")).strip(),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": job.get("salaryCurrency") or None,
        "salary_period_id": _to_int(job.get("salaryPeriodId")),
        "employment_type": employment_type,
        "experience_years": _to_int(job.get("yearsOfExperience")),
        "job_description": str(job.get("jobDescription", "")).strip(),
        "job_requirement": str(job.get("jobRequirement", "")).strip(),
        "job_function": job.get("jobFunction") or None,
        "skills": skills,
        "benefits": benefits,
        "posted_at": _parse_date(job.get("createdOn")),
        "approved_at": _parse_date(job.get("approvedOn")),
        "expired_at": _parse_date(job.get("expiredOn")),
        "is_active": is_active,
        "source": "vietnamworks",
    }


def _build_request_body(
    params: dict[str, Any], page: int, hits_per_page: int
) -> dict[str, Any]:
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

    items: list[dict[str, Any]] = []
    for index, job in enumerate(data):
        try:
            items.append(_normalize_job(job))
        except Exception as exc:
            logger.warning(
                "vietnamworks: skipping malformed job at index %d: %s", index, exc
            )
    return items


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": config.VIETNAMWORKS_USER_AGENT,
        "Accept": "application/json",
    }


_REQUEST_TIMEOUT = min(getattr(config, "VIETNAMWORKS_TIMEOUT_S", 60.0), 60.0)


async def _do_request(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> httpx.Response:
    return await asyncio.wait_for(
        client.post(
            _API_URL,
            json=body,
            headers=_headers(),
            timeout=httpx.Timeout(_REQUEST_TIMEOUT),
        ),
        timeout=_REQUEST_TIMEOUT,
    )


async def _scrape(params: dict[str, Any]) -> dict[str, Any]:
    max_items = int(params.get("max_items", 50) or 0)
    starting_page = int(params.get("page", 1) or 1)

    # If the caller explicitly passes a page, default to fetching just that page.
    default_max_pages = 1 if "page" in params else config.VIETNAMWORKS_MAX_PAGES
    max_pages_param = params.get("max_pages", default_max_pages)
    if max_pages_param in (None, ""):
        max_pages = default_max_pages
    else:
        max_pages = int(max_pages_param)

    if max_pages <= 0 or max_items == 0:
        return {
            "items": [],
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 0,
            "meta": None,
        }

    hits_per_page_param = params.get("hitsPerPage", 100)
    if hits_per_page_param in (None, ""):
        hits_per_page = 100
    else:
        hits_per_page = int(hits_per_page_param)
    if hits_per_page <= 0:
        return {
            "items": [],
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 0,
            "meta": None,
        }
    hits_per_page = min(hits_per_page, config.VIETNAMWORKS_MAX_ITEMS)

    items: list[dict[str, Any]] = []
    last_envelope: dict[str, Any] | None = None

    retry_attempts = getattr(config, "VIETNAMWORKS_RETRY_ATTEMPTS", 2)
    retry_backoff = getattr(config, "VIETNAMWORKS_RETRY_BACKOFF_BASE_S", 0.5)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            for page in range(starting_page, starting_page + max_pages):
                # Limit the page size so we don't over-fetch on the last page.
                remaining = max(0, max_items - len(items))
                if remaining == 0:
                    break
                page_size = min(hits_per_page, remaining)

                body = _build_request_body(params, page, page_size)
                resp: httpx.Response | None = None

                for attempt in range(retry_attempts + 1):
                    try:
                        resp = await _do_request(client, body)
                        if resp.status_code == 429:
                            if attempt < retry_attempts:
                                await asyncio.sleep(retry_backoff * (2**attempt))
                                continue
                            # Exceeded retry budget for this page.
                            return _degraded("rate_limited", items=items)
                        break
                    except httpx.TimeoutException:
                        return _degraded("timeout", items=items)

                if resp is None:  # pragma: no cover - defensive only
                    return _degraded("api_error", items=items)

                if resp.status_code in (403, 451):
                    return _degraded("access_blocked", items=items)
                if resp.status_code >= 500:
                    return _degraded("api_error", items=items)

                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "vietnamworks unexpected status %s: %s",
                        exc.response.status_code,
                        exc,
                    )
                    return _degraded("api_error", items=items)

                try:
                    envelope = resp.json()
                except Exception as exc:
                    logger.warning("vietnamworks response decode failed: %s", exc)
                    return _degraded("decode_error", items=items)

                if not isinstance(envelope, dict):
                    return _degraded("decode_error", items=items)

                last_envelope = envelope

                page_items = _extract_items(envelope)
                if not page_items:
                    break

                items.extend(page_items)
                if len(items) >= max_items:
                    break

                meta = envelope.get("meta") or {}
                nb_pages = meta.get("nbPages")
                if nb_pages is not None and page >= int(nb_pages):
                    break

                # Don't sleep after the last page.
                if page < starting_page + max_pages - 1:
                    await asyncio.sleep(config.VIETNAMWORKS_PAGE_DELAY_S)

    except (httpx.TimeoutException, TimeoutError):
        return _degraded("timeout", items=items)
    except httpx.ConnectError as exc:
        logger.warning("vietnamworks connect error: %s", exc)
        return _degraded("api_error", items=items)
    except ValueError as exc:
        logger.warning("vietnamworks response schema drift: %s", exc)
        return _degraded("schema_drift", items=items)
    except Exception as exc:
        logger.warning("vietnamworks.scrape failed: %s", exc)
        return _degraded("api_error", items=items)

    # Clamp to max_items if the API returned more than requested.
    items = items[:max_items]

    return {
        "items": items,
        "cost_micros": 0,
        "degraded": False,
        "degradation_reason": None,
        "total_items": len(items),
        "meta": (last_envelope or {}).get("meta"),
    }


async def scrape_vietnamworks(params: dict[str, Any]) -> dict[str, Any]:
    """Call VietnamWorks ``POST /job-search/v1.0/search`` and return normalized items."""
    try:
        return await _scrape(params)
    except ValueError as exc:
        logger.warning("vietnamworks response schema drift: %s", exc)
        return _degraded("schema_drift")
    except Exception as exc:
        logger.warning("vietnamworks.scrape failed: %s", exc)
        return _degraded("api_error")
