"""Normalize raw source outputs into ``VnJobAggregatedListing``."""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from typing import Any

from app.services.location_normalize import resolve_city_code

from .schemas import VnJobAggregatedListing, VnJobSalary

_SALARY_PERIOD_MAP: dict[int | str, str] = {
    1: "hour",
    2: "month",
    3: "year",
    4: "year",
    "hour": "hour",
    "month": "month",
    "year": "year",
    "negotiable": "negotiable",
    "hidden": "hidden",
}


def _parse_post_date(value: Any) -> datetime.date | None:
    """Parse source posted-date values into a UTC date."""
    if value is None:
        return None

    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value

    if isinstance(value, datetime.datetime):
        return value.date()

    text = str(value).lower().strip()
    today = datetime.date.today()
    if text in {"hôm nay", "today"}:
        return today
    if text in {"hôm qua", "yesterday"}:
        return today - datetime.timedelta(days=1)
    m = re.match(r"(\d+)\s+ngày\s+trước", text)
    if m:
        return today - datetime.timedelta(days=int(m.group(1)))

    # ISO / common absolute formats.
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        pass

    return None


_SALARY_PERIOD_BY_TEXT: list[tuple[tuple[str, ...], str]] = [
    (("/giờ", "/gio", "/h", " per hour", " per hr", "/hour"), "hour"),
    (("/ngày", "/ngay", " per day", "/day"), "day"),
    (("/tuần", "/tuan", " per week", "/week"), "week"),
    (("/tháng", "/thang", " per month", "/month", " monthly"), "month"),
    (("/năm", "/nam", " per year", "/year", " annually"), "year"),
]


def _infer_salary_period_from_text(text: str | None) -> str | None:
    """Infer salary period from raw Vietnamese/English salary text.

    Returns None when no period keyword is present.
    """
    if not text:
        return None
    lowered = text.lower()
    for keywords, period in _SALARY_PERIOD_BY_TEXT:
        if any(k in lowered for k in keywords):
            return period
    return None


def _normalize_salary_period(raw: Any, text: str | None = None) -> str:
    """Map source salary period identifiers to the common schema.

    When the source ``salary_period_id`` is inconsistent with the raw text
    (e.g. VietnamWorks text says "/tháng" but id maps to hour), infer from
    the text because that is what the user actually reads.
    """
    inferred = _infer_salary_period_from_text(text)
    if inferred:
        return inferred
    if raw is None:
        return "month"
    return _SALARY_PERIOD_MAP.get(raw, "month")


def _parse_salary(raw: dict[str, Any]) -> VnJobSalary:
    """Build a ``VnJobSalary`` from normalized source fields."""
    text = raw.get("salary_raw")
    salary = VnJobSalary(raw=text, confidence=0.0)

    min_val = raw.get("salary_min")
    max_val = raw.get("salary_max")

    # Distinguish "no salary data at all" (hidden) from "0/0 = negotiable".
    has_salary_fields = min_val is not None or max_val is not None

    if not text and not has_salary_fields:
        salary.period = "hidden"
        salary.confidence = 0.0
    elif text and ("thương lượng" in text.lower() or "negotiable" in text.lower()):
        salary.period = "negotiable"
        salary.confidence = 0.5
    elif not text and has_salary_fields:
        # No raw text but numeric fields present — derive from numbers.
        salary.period = _normalize_salary_period(raw.get("salary_period_id"))
        salary.confidence = 0.6
    else:
        salary.period = _normalize_salary_period(raw.get("salary_period_id"), text=text)
        salary.confidence = 0.6

    min_v = int(min_val) if min_val is not None else 0
    max_v = int(max_val) if max_val is not None else 0

    if min_v == 0 and max_v == 0:
        salary.min = 0
        salary.max = 0
        if salary.period not in ("negotiable", "hidden"):
            salary.period = "negotiable"
            salary.confidence = 0.5
    elif min_v > 0 and max_v == 0:
        salary.min = min_v
        salary.max = None
        salary.confidence = 0.7
    else:
        salary.min = min_v if min_v > 0 else None
        salary.max = max_v if max_v > 0 else None
        salary.confidence = 0.8

    salary.currency = raw.get("salary_currency") or "VND"
    return salary


def _normalize_location(raw: Any) -> str | None:
    """Normalize a location value to a canonical city code when possible.

    Falls back to the raw string for unknown cities so the aggregator-level
    filter still works on a best-effort basis.
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    code = resolve_city_code(text)
    return code or text


def _normalize_experience(raw: Any) -> int | None:
    """Parse experience-years text into an int.

    Handles:
    - int passthrough (5 → 5)
    - "3+ years" / "3 years" / "3 năm" → 3
    - "Không yêu cầu" / "no experience" → 0
    - None / unparseable → None
    """
    if raw is None:
        return None
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, float):
        return int(raw)
    text = str(raw).strip().lower()
    if not text:
        return None
    if any(
        w in text for w in ("không yêu cầu", "no experience", "khong yeu cau", "entry")
    ):
        return 0
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _derive_source_record_id(source: str, raw: dict[str, Any]) -> str:
    """Return a stable source record id, prefixing a keyed digest when ``id`` is missing."""
    raw_id = raw.get("id")
    if raw_id is not None:
        return str(raw_id)

    # ponytail: fallback uses a deterministic hash of source identity fields
    # so the same raw record always maps to the same provenance key, and
    # distinct records from the same source do not collide.
    identity = {
        "source": source,
        "title": raw.get("title"),
        "company": raw.get("company"),
        "location": raw.get("location"),
        "employment_type": raw.get("employment_type"),
        "posted_at": raw.get("posted_at"),
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "salary_currency": raw.get("salary_currency"),
        "salary_period_id": raw.get("salary_period_id"),
        "source_url": raw.get("source_url"),
    }
    text = json.dumps(
        {k: v for k, v in identity.items() if v is not None},
        sort_keys=True,
        default=str,
    )
    return f"{source}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def normalize_listing(source: str, raw: dict[str, Any]) -> VnJobAggregatedListing:
    """Convert a raw source listing into the common aggregator schema."""
    listing_id = _derive_source_record_id(source, raw)

    title = str(raw.get("title", "")).strip()
    company = str(raw.get("company", "")).strip()

    listing = VnJobAggregatedListing(
        id=str(listing_id),
        title=title,
        company=company,
        location=_normalize_location(raw.get("location")),
        employment_type=raw.get("employment_type"),
        experience_years=_normalize_experience(raw.get("experience_years")),
        skills=raw.get("skills") or [],
        salary=_parse_salary(raw),
        posted_at=_parse_post_date(raw.get("posted_at")),
        job_description=_normalize_text(raw.get("job_description")),
        job_requirement=_normalize_text(raw.get("job_requirement")),
        source=source,  # type: ignore[arg-type]
        source_urls=[u for u in [raw.get("source_url")] if u],
        confidence_score=0.6 if title and company else 0.3,
    )
    # ponytail: PrivateAttrs carry provenance without leaking into API output.
    listing._source_record_ids = {source: str(listing_id)}
    source_url = raw.get("source_url")
    if source_url:
        listing._source_url_map = {source: source_url}
    return listing
