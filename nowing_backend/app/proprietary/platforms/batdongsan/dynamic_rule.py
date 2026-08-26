from __future__ import annotations

import logging
from typing import Any

from app.config import config
from app.db import async_session_maker
from app.services.scraper_rule_cache import (
    get as get_cached_rule,
    set as set_cached_rule,
)
from app.services.scraper_rules_service import get_active_rule_schema

logger = logging.getLogger(__name__)

_DEFAULT_RULE: dict[str, Any] = {
    "selectors": {},
    "regexes": {},
    "delays": {"request_ms": 1500, "retry_base_ms": 1000},
    "retries": {"max_attempts": 3, "statuses": [403, 429, 500, 502, 503]},
    "circuit_breaker": {
        "error_threshold_pct": 20,
        "min_calls": 10,
        "trip_duration_seconds": 300,
        "tripped": False,
    },
}


def is_dynamic_rule_enabled() -> bool:
    return getattr(config, "USE_DYNAMIC_SCRAPER_RULES", False)


async def get_batdongsan_rule() -> dict[str, Any]:
    """Return the active batdongsan rule from cache or DB, else the default."""
    if not is_dynamic_rule_enabled():
        return _DEFAULT_RULE

    cached = get_cached_rule("batdongsan")
    if cached is not None:
        return cached

    try:
        async with async_session_maker() as session:
            rule_schema = await get_active_rule_schema(session, "batdongsan")
    except Exception:
        logger.exception("Failed to load batdongsan rule from database")
        return _DEFAULT_RULE

    if rule_schema is not None:
        set_cached_rule("batdongsan", rule_schema)
        return rule_schema

    return _DEFAULT_RULE
