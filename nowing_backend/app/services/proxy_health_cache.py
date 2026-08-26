"""Process-local cache for proxy health snapshots.

A simple in-memory TTL cache so dashboard polling does not hammer the proxy
endpoint. TTL is intentionally short (10s) to keep the dashboard reasonably
live while respecting the "read-only and throttled" requirement.
"""

from __future__ import annotations

import time
from typing import Any

_PROXY_CACHE_TTL_SECONDS = 10
_cached_at: float = 0.0
_cached_value: dict[str, Any] | None = None


def get_proxy_health_snapshot() -> dict[str, Any] | None:
    """Return the cached proxy health snapshot if still fresh."""
    global _cached_at, _cached_value
    if (
        _cached_value is None
        or (time.monotonic() - _cached_at) > _PROXY_CACHE_TTL_SECONDS
    ):
        return None
    return _cached_value


def update_proxy_health_snapshot(value: dict[str, Any]) -> None:
    """Store a proxy health snapshot and reset the TTL."""
    global _cached_at, _cached_value
    _cached_value = value
    _cached_at = time.monotonic()
