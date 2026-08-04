"""Rule-based confidence/trust scoring for aggregated BĐS listings."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from statistics import StatisticsError, mean, stdev
from typing import Any

from .normalize import _parse_post_date
from .schemas import VnBdsAggregatedListing

logger = logging.getLogger(__name__)

SOURCE_TRUST_WEIGHTS: dict[str, float] = {
    "batdongsan": 0.45,
    "chotot_bds": 0.30,
    "muaban_bds": 0.25,
}

OVERLAP_WEIGHT = 0.25
FRESHNESS_WEIGHT = 0.20
PRICE_CONSISTENCY_WEIGHT = 0.30
SOURCE_TRUST_COMPONENT_WEIGHT = 0.25

PRICE_CONFLICT_PENALTY = 0.7
FRESHNESS_HALF_LIFE_DAYS = 28


def _source_trust(sources: list[str]) -> float:
    if not sources:
        return 0.0
    weights = [SOURCE_TRUST_WEIGHTS.get(s, 0.30) for s in sources]
    return sum(weights) / len(weights)


def _overlap_score(source_count: int) -> float:
    return min(source_count, 3) / 3.0


def _freshness_score(post_date: str | None) -> float:
    if not post_date:
        return 0.5

    _, parsed = _parse_post_date(post_date)
    if parsed is None:
        return 0.5

    now = datetime.now(UTC)
    delta = now - parsed
    days = max(0.0, delta.total_seconds() / 86_400)
    if days <= 0:
        return 1.0

    score = math.exp(-math.log(2) * days / FRESHNESS_HALF_LIFE_DAYS)
    return round(max(0.0, min(1.0, score)), 4)


def _price_consistency_score(source_prices: dict[str, Any]) -> float:
    values = [int(v) for v in source_prices.values() if v is not None]
    if not values:
        return 0.5
    if len(values) == 1:
        return 1.0

    avg = mean(values)
    if avg == 0:
        return 0.0

    try:
        std = stdev(values)
    except StatisticsError:  # pragma: no cover - handled by len check
        return 1.0

    cv = std / avg
    score = 1.0 - min(cv, 1.0)
    return round(max(0.0, score), 4)


def score_listing(listing: VnBdsAggregatedListing) -> VnBdsAggregatedListing:
    """Populate the confidence and component scores on ``listing``."""
    listing.source_trust = _source_trust(listing.sources)
    listing.overlap_score = _overlap_score(listing.source_count)
    listing.freshness_score = _freshness_score(listing.post_date)
    listing.price_consistency_score = _price_consistency_score(listing.source_prices)

    confidence = (
        SOURCE_TRUST_COMPONENT_WEIGHT * listing.source_trust
        + OVERLAP_WEIGHT * listing.overlap_score
        + FRESHNESS_WEIGHT * listing.freshness_score
        + PRICE_CONSISTENCY_WEIGHT * listing.price_consistency_score
    )

    if listing.conflict_flags:
        confidence *= PRICE_CONFLICT_PENALTY

    listing.confidence_score = round(max(0.0, min(1.0, confidence)), 4)
    return listing
