"""Default scoring rubric and helpers for lead scoring (Story 21.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

DEFAULT_FIT_WEIGHTS: dict[str, float] = {
    "company_size": 20.0,
    "industry": 20.0,
    "location": 20.0,
    "tech_stack": 20.0,
    "icp": 20.0,
}

DEFAULT_INTENT_WEIGHTS: dict[str, float] = {
    "funding": 35.0,
    "hiring": 25.0,
    "tech_stack": 20.0,
    "executive_move": 15.0,
    "news": 5.0,
}


def recency_multiplier(days_ago: float) -> float:
    """Return a decayed weight for a signal based on its age.

    Default: 7d=1.0, 30d=0.7, 90d=0.4, older=0.1.
    """
    if days_ago <= 7:
        return 1.0
    if days_ago <= 30:
        return 0.7
    if days_ago <= 90:
        return 0.4
    return 0.1


def days_ago(detected_at: datetime) -> float:
    """Days between ``detected_at`` and now."""
    now = datetime.now(UTC)
    if detected_at.tzinfo is None:
        detected_at = detected_at.replace(tzinfo=UTC)
    return max(0.0, (now - detected_at).total_seconds() / 86400.0)


def clamp_score(value: float) -> float:
    """Clamp a score to [0, 100]."""
    return max(0.0, min(100.0, float(value)))


def classify(score: float) -> str:
    """Classify a composite score into hot/warm/cold."""
    if score >= 80.0:
        return "hot"
    if score >= 50.0:
        return "warm"
    return "cold"


def compute_trend(previous: float | None, current: float) -> str | None:
    """Return improving/stable/declining given previous and current score."""
    if previous is None:
        return None
    delta = current - previous
    if abs(delta) < 5.0:
        return "stable"
    if delta >= 5.0:
        return "improving"
    return "declining"


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize a weight map so the values sum to 1.0."""
    total = sum(weights.values())
    if total <= 0:
        return dict.fromkeys(weights, 0.0)
    return {k: v / total for k, v in weights.items()}


def default_icp_criteria() -> dict[str, Any]:
    """Return a neutral ICP criteria shape when none is configured."""
    return {
        "target_industries": [],
        "target_locations": [],
        "target_company_sizes": {},
        "target_tech_stack": [],
        "weights": dict(DEFAULT_FIT_WEIGHTS),
    }
