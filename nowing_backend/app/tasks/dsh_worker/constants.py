"""DSH worker constants."""

from __future__ import annotations

from app.config import config

# Hard 60s ceiling on every synchronous Redis stream / REST round-trip (AC-2 / AD-108).
_DSH_CALL_TIMEOUT_SECONDS = 60.0
_DSH_SYNC_TIMEOUT = min(
    float(getattr(config, "DSH_SYNC_TIMEOUT_SECONDS", _DSH_CALL_TIMEOUT_SECONDS)),
    _DSH_CALL_TIMEOUT_SECONDS,
)

_RENEW_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
else
    return 0
end
"""
