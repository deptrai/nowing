from __future__ import annotations

import time
from typing import Any

DEFAULT_TTL_SECONDS = 5

_cache: dict[str, tuple[Any, float]] = {}


def get(platform: str) -> Any:
    """Return the cached rule for a platform, or None if missing/expired."""
    entry = _cache.get(platform)
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        _cache.pop(platform, None)
        return None
    return value


def set(platform: str, value: Any, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
    """Cache a rule for a platform with a TTL (default 5s)."""
    _cache[platform] = (value, time.monotonic() + ttl_seconds)


def invalidate(platform: str) -> None:
    """Remove a platform from the in-memory cache."""
    _cache.pop(platform, None)
