"""Deduplicate job listings across sources and detect salary/location conflicts."""

from __future__ import annotations

from collections import defaultdict

from .schemas import VnJobAggregatedListing


def _canonical_key(listing: VnJobAggregatedListing) -> tuple[str, str, str, str | None]:
    """Deduplication key: company + title + location + posted_at (date)."""
    posted = listing.posted_at.isoformat() if listing.posted_at else None
    return (
        listing.company.lower().strip(),
        listing.title.lower().strip(),
        (listing.location or "").lower().strip(),
        posted,
    )


def deduplicate(listings: list[VnJobAggregatedListing]) -> list[VnJobAggregatedListing]:
    """Group listings by canonical key and merge cross-source variants."""
    groups: dict[tuple[str, str, str, str | None], list[VnJobAggregatedListing]] = defaultdict(list)
    for listing in listings:
        groups[_canonical_key(listing)].append(listing)

    merged: list[VnJobAggregatedListing] = []
    for group in groups.values():
        base = group[0]
        if len(group) > 1:
            base.source = "multiple"  # type: ignore[assignment]
            base.source_urls = list({url for item in group for url in item.source_urls})
            base.confidence_score = min(1.0, base.confidence_score + 0.1 * (len(group) - 1))
            # TODO: salary consistency scoring
            base.salary_consistency_score = 0.5
            base.conflict = _detect_conflict(group)
        merged.append(base)
    return merged


def _detect_conflict(group: list[VnJobAggregatedListing]) -> bool:
    """Detect material salary or location conflicts across sources."""
    salaries = [item.salary.max for item in group if item.salary.max is not None]
    locations = {item.location for item in group}
    if len(salaries) > 1 and max(salaries) - min(salaries) > 0.2 * max(salaries):
        return True
    return len(locations) > 1
