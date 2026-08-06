"""Normalize raw source outputs into ``VnJobAggregatedListing``."""

from __future__ import annotations

import datetime
import re
from typing import Any

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


def _normalize_salary_period(raw: Any) -> str:
    """Map source salary period identifiers to the common schema."""
    if raw is None:
        return "month"
    return _SALARY_PERIOD_MAP.get(raw, "month")


def _parse_salary(raw: dict[str, Any]) -> VnJobSalary:
    """Build a ``VnJobSalary`` from normalized source fields."""
    text = raw.get("salary_raw")
    salary = VnJobSalary(raw=text, confidence=0.0)

    if not text:
        salary.period = "hidden"
    elif "thương lượng" in text.lower() or "negotiable" in text.lower():
        salary.period = "negotiable"
        salary.confidence = 0.5
    else:
        salary.period = _normalize_salary_period(raw.get("salary_period_id"))
        salary.confidence = 0.6

    min_val = raw.get("salary_min")
    max_val = raw.get("salary_max")

    # VietnamWorks uses 0/0 for negotiable; keep both 0 in that case.
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
    """Normalize a location value to a common string."""
    if not raw:
        return None
    return str(raw).strip() or None


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_listing(source: str, raw: dict[str, Any]) -> VnJobAggregatedListing:
    """Convert a raw source listing into the common aggregator schema."""
    listing_id = raw.get("id")
    if listing_id is None:
        listing_id = f"{source}:unknown"

    title = str(raw.get("title", "")).strip()
    company = str(raw.get("company", "")).strip()

    listing = VnJobAggregatedListing(
        id=str(listing_id),
        title=title,
        company=company,
        location=_normalize_location(raw.get("location")),
        employment_type=raw.get("employment_type"),
        experience_years=raw.get("experience_years"),
        skills=raw.get("skills", []),
        salary=_parse_salary(raw),
        posted_at=_parse_post_date(raw.get("posted_at")),
        job_description=_normalize_text(raw.get("job_description")),
        job_requirement=_normalize_text(raw.get("job_requirement")),
        source=source,  # type: ignore[arg-type]
        source_urls=[raw.get("source_url", "")],
        confidence_score=0.6 if title and company else 0.3,
    )
    # ponytail: PrivateAttrs carry provenance without leaking into API output.
    listing._source_record_ids = {source: str(listing_id)}
    source_url = raw.get("source_url")
    if source_url:
        listing._source_url_map = {source: source_url}
    return listing
