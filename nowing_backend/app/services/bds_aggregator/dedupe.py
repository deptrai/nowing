"""Deduplicate and merge listings from multiple BĐS sources."""

from __future__ import annotations

import hashlib
import json
import logging
from statistics import mean
from typing import Any

from .normalize import _parse_post_date, make_canonical_id
from .schemas import ConflictFlag, VnBdsAggregatedListing

logger = logging.getLogger(__name__)


def _most_recent_date(a: str | None, b: str | None) -> str | None:
    """Pick the more recent post_date string between two raw values."""
    if not a:
        return b
    if not b:
        return a
    _, da = _parse_post_date(a)
    _, db = _parse_post_date(b)
    if da is None:
        return b
    if db is None:
        return a
    return a if da >= db else b


def _format_price(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} Tỷ".rstrip("0").rstrip(".") + " Tỷ"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.0f} Triệu"
    return f"{value}"


def _coalesce(a: Any, b: Any) -> Any:
    return a if a is not None and a != "" else b


def _merge_two(
    a: VnBdsAggregatedListing, b: VnBdsAggregatedListing
) -> VnBdsAggregatedListing:
    """Merge ``b`` into ``a`` and return a new listing."""
    source_ids = {**a.source_ids, **b.source_ids}
    detail_urls = {**a.detail_urls, **b.detail_urls}
    sources = sorted({*a.sources, *b.sources})
    source_prices = {**a.source_prices, **b.source_prices}

    title = a.title
    if b.title and (not a.title or len(b.title) > len(a.title)):
        title = b.title

    # Keep the longest / most informative location components.
    district = _coalesce(a.district, b.district)
    ward = _coalesce(a.ward, b.ward)
    city = _coalesce(a.city, b.city)
    location = _coalesce(a.location, b.location)
    project = _coalesce(a.project, b.project)
    legal = _coalesce(a.legal, b.legal)

    # Prefer a non-empty thumbnail from any source.
    thumbnail_url = _coalesce(a.thumbnail_url, b.thumbnail_url)

    # Use the most recent post date.
    post_date = _most_recent_date(a.post_date, b.post_date)

    # Pick any available contact/masked phone; the source with a phone wins.
    contact = _coalesce(a.contact, b.contact)
    phone_key = _coalesce(a.phone_key, b.phone_key)
    address_key = _coalesce(a.address_key, b.address_key)
    image_key = _coalesce(a.image_key, b.image_key)

    # Average area when both are present; otherwise keep the single value.
    if a.area_value is not None and b.area_value is not None:
        area_value = (a.area_value + b.area_value) / 2
        area = _coalesce(a.area, b.area)
    else:
        area_value = _coalesce(a.area_value, b.area_value)
        area = _coalesce(a.area, b.area)

    # Canonical price is the mean across all source prices; we'll recompute.
    merged = VnBdsAggregatedListing(
        canonical_id=make_canonical_id(source_ids),
        source_ids=source_ids,
        title=title,
        price=_coalesce(a.price, b.price),
        price_value=None,  # computed below
        price_per_m2=None,
        area=area,
        area_value=area_value,
        location=location,
        district=district,
        ward=ward,
        city=city,
        project=project,
        legal=legal,
        post_date=post_date,
        contact=contact,
        phone_key=phone_key,
        address_key=address_key,
        image_key=image_key,
        source_prices=source_prices,
        thumbnail_url=thumbnail_url,
        detail_urls=detail_urls,
        sources=sources,
        source_count=len(sources),
        confidence_score=0.0,
        provenance=_coalesce(a.provenance, b.provenance),
    )
    return _recompute_price_fields(merged)


def _recompute_price_fields(listing: VnBdsAggregatedListing) -> VnBdsAggregatedListing:
    """Set price_value, price, and price_per_m2 from collected source prices."""
    values = [v for v in listing.source_prices.values() if v is not None]
    if values:
        price_value = int(mean(values))
        listing.price_value = price_value
        if listing.price is None:
            listing.price = _format_price(price_value)
        if listing.area_value and listing.area_value > 0:
            listing.price_per_m2 = price_value / listing.area_value
    else:
        listing.price_value = None
        if listing.price is None:
            listing.price = None
    return listing


def _detect_price_conflict(listing: VnBdsAggregatedListing) -> VnBdsAggregatedListing:
    """Add a price_conflict flag when source prices diverge beyond 20%."""
    values = [v for v in listing.source_prices.values() if v is not None]
    if len(values) < 2:
        return listing

    min_price = min(values)
    max_price = max(values)
    avg = mean(values)

    if avg == 0:
        return listing

    ratio = max_price / min_price if min_price else float("inf")
    relative_diff = (max_price - min_price) / avg

    if ratio > 1.2 or relative_diff > 0.2:
        reason = (
            f"Price varies {ratio:.2f}x across sources "
            f"(min={min_price:,}, max={max_price:,} VND)"
        )
        flag = ConflictFlag(
            reason=reason,
            price_range={"min": min_price, "max": max_price},
            price_sources=dict(listing.source_prices),
        )
        listing.conflict_flags.append(flag)

    return listing


def merge_group(listings: list[VnBdsAggregatedListing]) -> VnBdsAggregatedListing:
    """Reduce a list of matched listings into one aggregated listing."""
    if not listings:
        raise ValueError("cannot merge an empty group")
    merged = listings[0]
    for other in listings[1:]:
        merged = _merge_two(merged, other)
    merged = _detect_price_conflict(merged)
    return merged


def deduplicate(listings: list[VnBdsAggregatedListing]) -> list[VnBdsAggregatedListing]:
    """Group and merge listings by phone, address, or image hash.

    Uses a union-find structure so that transitive matches are merged into a
    single canonical group (e.g. A matches B by phone, B matches C by address,
    therefore A, B and C are the same listing).
    """
    if not listings:
        return []

    parent = list(range(len(listings)))

    def _find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def _union(i: int, j: int) -> None:
        root_i, root_j = _find(i), _find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    # Build an index of keys -> first listing index that has the key.
    phone_index: dict[str, int] = {}
    address_index: dict[str, int] = {}
    image_index: dict[str, int] = {}

    for idx, listing in enumerate(listings):
        if listing.phone_key:
            if listing.phone_key in phone_index:
                _union(idx, phone_index[listing.phone_key])
            else:
                phone_index[listing.phone_key] = idx
        if listing.address_key:
            if listing.address_key in address_index:
                _union(idx, address_index[listing.address_key])
            else:
                address_index[listing.address_key] = idx
        if listing.image_key:
            if listing.image_key in image_index:
                _union(idx, image_index[listing.image_key])
            else:
                image_index[listing.image_key] = idx

    clusters: dict[int, list[VnBdsAggregatedListing]] = {}
    for idx, listing in enumerate(listings):
        root = _find(idx)
        clusters.setdefault(root, []).append(listing)

    return [merge_group(cluster) for cluster in clusters.values()]


def fingerprint(raw_data: dict[str, Any]) -> str:
    """Stable canonical fingerprint for a raw BĐS listing.

    Reuses the existing canonical-id generator over the most stable source
    identity when available, and falls back to a sorted hash of the title and
    location for records without a usable id.
    """
    from .normalize import _extract_id, _normalize_address, _source_title

    source_id = _extract_id(raw_data)
    if source_id is not None:
        return make_canonical_id({"bds": source_id})

    # Fallback for raw records that have not been assigned an id yet.
    title = (_source_title(raw_data, "bds") or "").strip().lower()
    address = (
        _normalize_address(
            raw_data.get("district"),
            raw_data.get("ward"),
            raw_data.get("location"),
        )
        or ""
    )
    payload = json.dumps(
        {"title": title, "address": address},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _to_aggregated_listing(raw_data: dict[str, Any]) -> VnBdsAggregatedListing:
    """Best-effort normalization of a raw dict for merge/search_text."""
    from .normalize import normalize_listing

    return normalize_listing(raw_data.get("source", "bds"), raw_data)


def merge(
    canonical: VnBdsAggregatedListing | dict[str, Any],
    new_raw: dict[str, Any],
) -> VnBdsAggregatedListing:
    """Merge ``new_raw`` into ``canonical`` using the existing merge logic."""
    if isinstance(canonical, dict):
        canonical = _to_aggregated_listing(canonical)
    new_listing = _to_aggregated_listing(new_raw)
    return merge_group([canonical, new_listing])


def search_text(canonical: VnBdsAggregatedListing | dict[str, Any]) -> str:
    """Return a single searchable text for a BĐS canonical entity."""
    if isinstance(canonical, dict):
        canonical = _to_aggregated_listing(canonical)
    parts = [
        canonical.title,
        canonical.location,
        canonical.district,
        canonical.ward,
        canonical.city,
        canonical.project,
        canonical.legal,
        canonical.price,
        canonical.area,
    ]
    return " ".join(p for p in parts if p).strip()
