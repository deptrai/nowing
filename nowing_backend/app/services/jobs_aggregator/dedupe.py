"""Deduplicate job listings across sources and detect salary/location conflicts.

AC-4: Fuzzy title matching (Jaro-Winkler ≥ 0.85) + posted_at ±3 days + location normalization.
AC-5: Salary consistency (≤10% → stable, confidence ≥ 0.8) + source_count.
AC-6: Conflict flags (SALARY_MISMATCH / LOCATION_MISMATCH) + lower confidence + preserve both records.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from collections import defaultdict
from typing import Any

from rapidfuzz.distance import JaroWinkler

from app.services.location_normalize import resolve_city_code

from .schemas import VnJobAggregatedListing, VnJobSalary

_JW_THRESHOLD = 0.85
_DATE_TOLERANCE_DAYS = 3
_SALARY_STABLE_THRESHOLD = 0.10  # ≤10% → stable
_SALARY_CONFLICT_THRESHOLD = 0.20  # >20% → conflict


def _canonical_key(listing: VnJobAggregatedListing) -> tuple[str]:
    """Coarse grouping key: normalized company only.

    Location and title are checked in fine matching.  Grouping by company
    only allows None-location listings to match any location (wildcard).
    """
    return (listing.company.lower().strip(),)


def _fingerprint_key(listing: VnJobAggregatedListing) -> tuple[str, str, str]:
    """Canonical fingerprint key: title + company + resolved location.

    Two listings with the same title/company but different resolved locations
    represent distinct canonical entities and must not collide.
    """
    return (
        (listing.title or "").lower().strip(),
        listing.company.lower().strip(),
        resolve_city_code(listing.location)
        or (listing.location or "").lower().strip(),
    )


def _locations_compatible(a: str | None, b: str | None) -> bool:
    """True if locations match after normalization, or either is None (wildcard)."""
    if not a or not b:
        return True
    return resolve_city_code(a) == resolve_city_code(b)


def _titles_match(title_a: str, title_b: str) -> bool:
    """Jaro-Winkler similarity ≥ 0.85."""
    if not title_a or not title_b:
        return False
    return (
        JaroWinkler.similarity(title_a.lower().strip(), title_b.lower().strip())
        >= _JW_THRESHOLD
    )


def _dates_within_tolerance(a: datetime.date | None, b: datetime.date | None) -> bool:
    """True if both dates are within ±3 days, or either is None (skip constraint)."""
    if a is None or b is None:
        return True
    return abs((a - b).days) <= _DATE_TOLERANCE_DAYS


def _should_dedupe(a: VnJobAggregatedListing, b: VnJobAggregatedListing) -> bool:
    """Check if two listings in the same coarse group should be merged."""
    # Skip dedupe when company is empty — would group unrelated listings.
    if not a.company.strip() or not b.company.strip():
        return False
    if not _titles_match(a.title, b.title):
        return False
    if not _dates_within_tolerance(a.posted_at, b.posted_at):
        return False
    return _locations_compatible(a.location, b.location)


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


def _salary_values(group: list[VnJobAggregatedListing]) -> list[int]:
    """Extract non-zero salary values for comparison.

    Zero values mean "negotiable/hidden" and are skipped per Q4 failure mode.
    """
    values: list[int] = []
    for item in group:
        if item.salary.min and item.salary.min > 0:
            values.append(item.salary.min)
        if item.salary.max and item.salary.max > 0:
            values.append(item.salary.max)
    return values


def _salary_relative_spread(values: list[int]) -> float:
    """Relative spread = (max - min) / max(values). 0 if < 2 values."""
    if len(values) < 2:
        return 0.0
    lo, hi = min(values), max(values)
    if hi == 0:
        return 0.0
    return (hi - lo) / hi


def _detect_conflict(
    group: list[VnJobAggregatedListing],
) -> tuple[list[str], float, float]:
    """Return (conflict_flags, salary_consistency_score, confidence_score) for a group.

    conflict_flags: list of "SALARY_MISMATCH" / "LOCATION_MISMATCH"
    salary_consistency_score: 0.0-1.0
    confidence_score: 0.5-0.7 on conflict, >=0.8 when stable
    """
    if len(group) <= 1:
        return [], 0.5, group[0].confidence_score if group else 0.0

    flags: list[str] = []

    # --- Location mismatch ---
    # Normalize locations; None/empty are wildcards (not a real mismatch).
    loc_codes = {
        resolve_city_code(item.location) or (item.location or "").lower().strip()
        for item in group
        if item.location and item.location.strip()
    }
    if len(loc_codes) > 1:
        flags.append("LOCATION_MISMATCH")

    # --- Salary mismatch ---
    values = _salary_values(group)
    if len(values) >= 2:
        spread = _salary_relative_spread(values)
        if spread > _SALARY_CONFLICT_THRESHOLD:
            flags.append("SALARY_MISMATCH")
            # Confidence: 0.5 for very large spread (>50%), 0.7 for just above 20%.
            if spread > 0.5:
                confidence = 0.5
            else:
                confidence = round(0.7 - (spread - 0.2) * 0.5, 2)
                confidence = max(0.5, min(0.7, confidence))
            salary_consistency = round(max(0.0, 1.0 - spread), 2)
        elif spread <= _SALARY_STABLE_THRESHOLD:
            # Stable: ≤10% → confidence ≥ 0.8
            confidence = 0.8
            salary_consistency = round(1.0 - spread, 2)
        else:
            # Gray zone: 10%-20% -- no conflict flag, moderate confidence.
            confidence = 0.75
            salary_consistency = round(1.0 - spread, 2)
    elif len(values) == 1:
        # Only one salary value — can't compare, no conflict.
        confidence = 0.8
        salary_consistency = 0.9
    else:
        # No salary values (all hidden/negotiable/zero) — can't compare.
        confidence = 0.6
        salary_consistency = 0.5

    # Location mismatch lowers confidence further.
    if "LOCATION_MISMATCH" in flags and "SALARY_MISMATCH" not in flags:
        confidence = min(confidence, 0.6)
    elif "LOCATION_MISMATCH" in flags and "SALARY_MISMATCH" in flags:
        confidence = min(confidence, 0.5)

    return flags, salary_consistency, round(confidence, 2)


def _merge_group(group: list[VnJobAggregatedListing]) -> VnJobAggregatedListing:
    """Merge a group of listings into a single canonical listing."""
    base = group[0]
    if len(group) > 1:
        base.source = "multiple"  # type: ignore[assignment]
        base.source_urls = [url for item in group for url in item.source_urls if url]
        base.skills = list({skill.lower() for item in group for skill in item.skills})
        base.salary = _merge_salary(group)
        base.source_count = len(group)
        # ponytail: confidence boost for cross-source groups, capped at 1.0.
        # This is overridden by _detect_conflict if conflict is found.
        base.confidence_score = round(
            min(1.0, base.confidence_score + 0.1 * (len(group) - 1)), 2
        )
        # Merge provenance from every source in the group.
        merged_record_ids: dict[str, str] = {}
        merged_url_map: dict[str, str] = {}
        for item in group:
            merged_record_ids.update(item._source_record_ids)
            merged_url_map.update(item._source_url_map)
        base._source_record_ids = merged_record_ids
        base._source_url_map = merged_url_map

    flags, salary_consistency, confidence = _detect_conflict(group)
    base.conflict_flags = flags
    base.conflict = bool(flags)
    base.salary_consistency_score = salary_consistency
    if flags:
        base.confidence_score = confidence
    else:
        # No conflict: use the higher of boost or stable confidence.
        base.confidence_score = max(base.confidence_score, confidence)
    base.salary.confidence = round(base.salary.confidence * salary_consistency, 2)

    return base


def _union_find(n: int, pairs: list[tuple[int, int]]) -> list[int]:
    """Run union-find on n elements with the given merge pairs. Returns parent array."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in pairs:
        union(a, b)
    return parent


def deduplicate(listings: list[VnJobAggregatedListing]) -> list[VnJobAggregatedListing]:
    """Group listings by canonical key and merge cross-source variants.

    Uses Jaro-Winkler >= 0.85 for fuzzy title matching and +-3 days tolerance
    on posted_at.  Coarse grouping by company then fine matching within each
    group.

    ponytail: O(n^2) within each coarse group -- acceptable for <=20 per group.
    If a query returns 1000+ listings with one dominant company, this could
    be slow.  Upgrade path: sort by posted_at and window the comparison.
    """
    # Coarse grouping by company only (location checked in fine matching).
    coarse: dict[tuple[str], list[VnJobAggregatedListing]] = defaultdict(list)
    for listing in listings:
        coarse[_canonical_key(listing)].append(listing)

    merged: list[VnJobAggregatedListing] = []
    for group in coarse.values():
        # Fine matching within each coarse group using union-find.
        # ponytail: simple O(n^2) pairwise comparison within small groups.
        n = len(group)
        pairs: list[tuple[int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                if _should_dedupe(group[i], group[j]):
                    pairs.append((i, j))
        parent = _union_find(n, pairs)

        # Collect merged groups.
        fine_groups: dict[int, list[VnJobAggregatedListing]] = defaultdict(list)
        for i, item in enumerate(group):
            # Find root using the same path-compressed logic.
            root = i
            while parent[root] != root:
                root = parent[root]
            fine_groups[root].append(item)

        for fine_group in fine_groups.values():
            merged.append(_merge_group(fine_group))

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
    key = _fingerprint_key(listing)
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
