from __future__ import annotations

from typing import Any

from app.config import config
from app.services.scraper_rule_cache import get as get_cached_rule

_DEFAULT_RULE: dict[str, Any] = {
    "selectors": {},
    "regexes": {},
    "delays": {"request_ms": 1500, "retry_base_ms": 1000},
    "retries": {"max_attempts": 3, "statuses": [429, 500, 502, 503]},
    "circuit_breaker": {
        "error_threshold_pct": 20,
        "min_calls": 10,
        "trip_duration_seconds": 300,
        "tripped": False,
    },
}


def is_dynamic_rule_enabled() -> bool:
    return getattr(config, "USE_DYNAMIC_SCRAPER_RULES", False)


def get_batdongsan_rule() -> dict[str, Any]:
    """Return the active batdongsan rule if the feature flag is on, else default."""
    if not is_dynamic_rule_enabled():
        return _DEFAULT_RULE

    cached = get_cached_rule("batdongsan")
    if cached is not None:
        return cached

    return _DEFAULT_RULE
