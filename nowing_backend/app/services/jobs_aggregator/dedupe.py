"""Deduplicate job listings across sources and detect salary/location conflicts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from .schemas import VnJobAggregatedListing, VnJobSalary


def _canonical_key(listing: VnJobAggregatedListing) -> tuple[str, str, str, str | None]:
    """Deduplication key: company + title + location + posted_at (date)."""
    posted = listing.posted_at.isoformat() if listing.posted_at else None
    return (
        listing.company.lower().strip(),
        listing.title.lower().strip(),
        (listing.location or "").lower().strip(),
        posted,
    )


def _merge_salary(group: list[VnJobAggregatedListing]) -> VnJobSalary:
    """Combine salary evidence from all sources in a group."""
    mins = [item.salary.min for item in group if item.salary.min is not None]
    maxs = [item.salary.max for item in group if item.salary.max is not None]
    confidences = [
        item.salary.confidence for item in group if item.salary.confidence > 0
    ]
    raws = [item.salary.raw for item in group if item.salary.raw]

    merged = VnJobSalary(
        raw=raws[0] if raws else None,
        min=min(mins) if mins else None,
        max=max(maxs) if maxs else None,
        currency=group[0].salary.currency or "VND",
        period=group[0].salary.period,
        confidence=round(sum(confidences) / len(confidences), 2)
        if confidences
        else 0.0,
    )
    return merged


def _detect_conflict(group: list[VnJobAggregatedListing]) -> tuple[bool, float]:
    """Return (conflict, salary_consistency_score) for a deduplicated group."""
    salaries: list[VnJobSalary] = [
        item.salary
        for item in group
        if item.salary.max is not None or item.salary.min is not None
    ]
    locations = {item.location for item in group}

    # Conflict if multiple distinct locations.
    if len(locations) > 1:
        return True, 0.0

    if not salaries:
        return False, 0.5

    mins = [s.min for s in salaries if s.min is not None]
    maxs = [s.max for s in salaries if s.max is not None]

    if not maxs and not mins:
        return False, 0.5

    all_values = [v for v in (mins + maxs) if v is not None]
    if not all_values:
        return False, 0.5

    if len(all_values) == 1:
        return False, 0.9

    avg = sum(all_values) / len(all_values)
    spread = max(all_values) - min(all_values)
    if avg == 0:
        return False, 0.5

    relative_spread = spread / avg
    if relative_spread > 0.3:
        return True, round(max(0.0, 1.0 - relative_spread), 2)

    return False, round(max(0.0, 1.0 - relative_spread / 2), 2)


def deduplicate(listings: list[VnJobAggregatedListing]) -> list[VnJobAggregatedListing]:
    """Group listings by canonical key and merge cross-source variants."""
    groups: dict[tuple[str, str, str, str | None], list[VnJobAggregatedListing]] = (
        defaultdict(list)
    )
    for listing in listings:
        groups[_canonical_key(listing)].append(listing)

    merged: list[VnJobAggregatedListing] = []
    for group in groups.values():
        base = group[0]
        if len(group) > 1:
            base.source = "multiple"  # type: ignore[assignment]
            base.source_urls = [
                url for item in group for url in item.source_urls if url
            ]
            base.skills = list(
                {skill.lower() for item in group for skill in item.skills}
            )
            base.salary = _merge_salary(group)
            base.confidence_score = round(
                min(1.0, base.confidence_score + 0.1 * (len(group) - 1)), 2
            )
            # ponytail: merge provenance from every source in the group.
            merged_record_ids: dict[str, str] = {}
            merged_url_map: dict[str, str] = {}
            for item in group:
                merged_record_ids.update(item._source_record_ids)
                merged_url_map.update(item._source_url_map)
            base._source_record_ids = merged_record_ids
            base._source_url_map = merged_url_map

        conflict, salary_consistency = _detect_conflict(group)
        base.conflict = conflict
        base.salary_consistency_score = salary_consistency
        base.salary.confidence = round(base.salary.confidence * salary_consistency, 2)
        merged.append(base)

    return merged


def _raw_to_listing(raw: dict[str, Any]) -> VnJobAggregatedListing:
    """Best-effort normalization for a raw dict."""
    from .normalize import normalize_listing

    source = raw.get("source")
    if source not in ("vietnamworks", "topcv", "itviec"):
        source = "topcv"
    return normalize_listing(source, raw)


def fingerprint(raw_data: dict[str, Any]) -> str:
    """Stable canonical fingerprint for a raw job listing."""
    listing = _raw_to_listing(raw_data)
    key = _canonical_key(listing)
    payload = json.dumps(
        {i: v for i, v in enumerate(key) if v is not None},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def merge(
    canonical: VnJobAggregatedListing | dict[str, Any],
    new_raw: dict[str, Any],
) -> VnJobAggregatedListing:
    """Merge ``new_raw`` into ``canonical`` using the existing group logic."""
    if isinstance(canonical, dict):
        canonical = _raw_to_listing(canonical)
    new_listing = _raw_to_listing(new_raw)
    # Deduplicate resolves to one item when the canonical keys match.
    result = deduplicate([canonical, new_listing])
    return result[0] if result else canonical


def search_text(canonical: VnJobAggregatedListing | dict[str, Any]) -> str:
    """Return a single searchable text for a Jobs canonical entity."""
    if isinstance(canonical, dict):
        canonical = _raw_to_listing(canonical)
    parts = [
        canonical.title,
        canonical.company,
        canonical.location,
        ", ".join(canonical.skills),
        canonical.employment_type,
        canonical.job_description,
        canonical.job_requirement,
        canonical.salary.raw,
    ]
    return " ".join(p for p in parts if p).strip()
