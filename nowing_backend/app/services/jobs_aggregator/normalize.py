"""Normalize raw source outputs into ``VnJobAggregatedListing``."""

from __future__ import annotations

import datetime
import re
from typing import Any

from .schemas import VnJobAggregatedListing, VnJobSalary


def _parse_post_date(text: str | None) -> datetime.date | None:
    """Parse Vietnamese relative/absolute date strings into a UTC date."""
    if not text:
        return None
    text = text.lower().strip()
    today = datetime.date.today()
    if text in {"hôm nay", "today"}:
        return today
    if text in {"hôm qua", "yesterday"}:
        return today - datetime.timedelta(days=1)
    m = re.match(r"(\d+)\s+ngày\s+trước", text)
    if m:
        return today - datetime.timedelta(days=int(m.group(1)))
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_salary(text: str | None) -> VnJobSalary:
    """Skeleton salary parser. Returns low-confidence salary object."""
    salary = VnJobSalary(raw=text, confidence=0.0)
    if not text:
        salary.period = "hidden"
        return salary
    if "thương lượng" in text.lower() or "negotiable" in text.lower():
        salary.period = "negotiable"
        salary.confidence = 0.5
        return salary
    # TODO: parse "Từ X đến Y triệu", "$X - $Y", etc.
    return salary


def _normalize_location(raw: Any) -> str | None:
    """Normalize a location string to a common Vietnamese place name."""
    if not raw:
        return None
    return str(raw).strip()


def normalize_listing(source: str, raw: dict[str, Any]) -> VnJobAggregatedListing:
    """Convert a raw source listing into a common schema."""
    return VnJobAggregatedListing(
        id=f"{source}:{raw.get('id', 'unknown')}",
        title=str(raw.get("title", "")),
        company=str(raw.get("company", "")),
        location=_normalize_location(raw.get("location")),
        employment_type=raw.get("employment_type"),
        experience_years=raw.get("experience_years"),
        skills=raw.get("skills", []),
        salary=_parse_salary(raw.get("salary_raw")),
        posted_at=_parse_post_date(raw.get("posted_at")),
        job_description=raw.get("job_description"),
        job_requirement=raw.get("job_requirement"),
        source=source,  # type: ignore[arg-type]
        source_urls=[raw.get("source_url", "")],
    )
