import asyncio
import json
import logging
import os
import time

from app.services.crypto_cache_lock import get_redis_client

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    """Parse a float env var. Round 2 review fix: malformed values used to
    crash the entire module import (and therefore agent startup) because
    `float("abc")` raises. Now we log a warning and fall back to the default."""
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "rate_limiter: invalid value for %s=%r, falling back to default %s",
            name, raw, default,
        )
        return float(default)


# AC#6: Provider rate limits config with Env overrides (Review Patch #8)
PROVIDER_RATE_LIMITS = {
    "coingecko": {"capacity": _env_float("RL_COINGECKO_CAP", 30), "refill_rate": 0.5},    # 30/min
    "cryptopanic": {"capacity": _env_float("RL_CRYPTOPANIC_CAP", 60), "refill_rate": 1.0},  # 60/min
    "goplus": {"capacity": _env_float("RL_GOPLUS_CAP", 33), "refill_rate": 33 / 1800.0},   # 2000/day ≈ 33/30min (Review Patch #9)
    "etherscan": {"capacity": _env_float("RL_ETHERSCAN_CAP", 5), "refill_rate": 5.0},      # 5/sec (Review Patch #1)
    "defillama": {"capacity": _env_float("RL_DEFILLAMA_CAP", 120), "refill_rate": 2.0},    # generous
    "reddit": {"capacity": _env_float("RL_REDDIT_CAP", 60), "refill_rate": 1.0},          # 60/min
    "alternative_me": {"capacity": _env_float("RL_ALTERNATIVE_CAP", 30), "refill_rate": 0.5}, # conservative
}

# Lua script for atomic token bucket acquisition using Redis server time (Review Patch #4)
#
# Story 11.6 / ADR-011: returns `[acquired, tokens, last_refill]` so the Python
# caller can mirror Redis state into the local fallback bucket on every
# successful EVAL — eliminates the Redis-flap double-consume bug.
_ACQUIRE_SCRIPT = """
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])

-- Get Redis server time
local redis_time = redis.call("TIME")
local now = tonumber(redis_time[1]) + (tonumber(redis_time[2]) / 1000000)

local state = redis.call("HMGET", KEYS[1], "tokens", "last_refill")
local tokens = tonumber(state[1]) or capacity
local last_refill = tonumber(state[2]) or now

-- Refill tokens
local delta = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + (delta * refill_rate))

local acquired = 0
if tokens >= 1 then
    tokens = tokens - 1
    acquired = 1
end

redis.call("HMSET", KEYS[1], "tokens", tokens, "last_refill", now)
-- Set TTL to 1 hour to keep keys clean if unused
redis.call("EXPIRE", KEYS[1], 3600)

-- Return Redis-side state so Python can mirror it into the local fallback
-- bucket. Format: [acquired (0/1), tokens (float-as-string), last_refill (float-as-string)]
return {acquired, tostring(tokens), tostring(now)}
"""


# Lua script for atomic token release (Story 11.7 / 11.4 round-2 token-waste fix)
# Refills the bucket by `count` (capped at capacity) without touching
# `last_refill`, since a release does not represent a refill event — it just
# returns a previously-acquired token to the pool. Idempotent across retries.
_RELEASE_SCRIPT = """
local capacity = tonumber(ARGV[1])
local count = tonumber(ARGV[2])

local state = redis.call("HMGET", KEYS[1], "tokens", "last_refill")
local tokens = tonumber(state[1]) or capacity
local last_refill = tonumber(state[2])

tokens = math.min(capacity, tokens + count)

if last_refill == nil then
    local redis_time = redis.call("TIME")
    last_refill = tonumber(redis_time[1]) + (tonumber(redis_time[2]) / 1000000)
end

redis.call("HMSET", KEYS[1], "tokens", tokens, "last_refill", last_refill)
redis.call("EXPIRE", KEYS[1], 3600)

return tostring(tokens)
"""


class TokenBucketRateLimiter:
    """
    Per-provider rate limiter using Token Bucket algorithm.
    Shared across workers via Redis; falls back to local memory.
    """

    def __init__(self, provider: str, capacity: float, refill_rate: float):
        self.provider = provider
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.key = f"rl:{provider}:v1"

        # Local fallback state using monotonic time (Review Patch #3)
        self._local_tokens = capacity
        self._local_last_refill = time.monotonic()
        self._local_lock = asyncio.Lock()
        self._warned_redis = False
        # Story 11.6 round 2: Redis-side wall-clock of the most recent
        # successful EVAL we mirrored. Two concurrent acquires can finish
        # their EVAL out of order; we only apply the mirror write if the
        # Redis timestamp is newer than what's already mirrored, otherwise
        # an older response would clobber the freshest state and leak the
        # double-consume window the mirror was designed to close.
        self._last_redis_ts: float = 0.0

    async def acquire(self, timeout_s: float = 5.0) -> bool:
        """
        Attempt to acquire 1 token from the bucket.
        Waits up to timeout_s if bucket is empty.

        Returns True if a token was acquired, False on timeout.

        Round-2 review hardening:
        - Fail-fast when refill is too slow to ever satisfy `timeout_s`
          (e.g. goplus: 0.018 tok/s → 54s/token vs 5s budget).
        - Single throttle log per `acquire()` call (first wait + final timeout)
          rather than one per poll iteration.
        - Defensive integer cast on EVAL response and `max(0, ...)` on sleep.
        """
        start_time = time.perf_counter()
        first_wait_logged = False

        # Refill is so slow we can't possibly refill 1 token within the budget.
        # Don't waste cycles polling — fail-fast and let the caller fall back.
        unrefillable = self.refill_rate > 0 and (1.0 / self.refill_rate) > timeout_s

        while True:
            redis = get_redis_client()
            acquired = False

            if redis:
                try:
                    res = await redis.eval(
                        _ACQUIRE_SCRIPT,
                        1,
                        self.key,
                        self.capacity,
                        self.refill_rate,
                    )
                    # Story 11.6 / ADR-011: Lua returns [acquired, tokens, last_refill].
                    # Mirror Redis state into the local fallback bucket so a
                    # subsequent Redis-down iteration starts from the *current*
                    # remaining count (not a stale `capacity` snapshot) —
                    # eliminates the double-consume window during Redis flap.
                    #
                    # Round 2 fix: we use Redis's `last_refill` timestamp as
                    # an ordering guard so concurrent acquires can't apply
                    # mirror writes out of order. We do NOT use it for the
                    # local refill clock — `_local_last_refill` stays on
                    # `time.monotonic()` because Redis wall-clock and local
                    # monotonic are different clocks.
                    if isinstance(res, (list, tuple)) and len(res) >= 3:
                        try:
                            acquired = int(res[0]) == 1
                        except (TypeError, ValueError):
                            acquired = bool(res[0])
                        try:
                            redis_tokens = float(res[1])
                            redis_ts = float(res[2])
                        except (TypeError, ValueError, IndexError):
                            # Bad Lua response shape — treat as flap, do not
                            # update local mirror.
                            pass
                        else:
                            async with self._local_lock:
                                # Skip the mirror write if a fresher response
                                # has already landed: prevents the TOCTOU
                                # double-consume regression where a stale
                                # higher token count clobbers a fresh lower
                                # one under concurrent acquires.
                                if redis_ts >= self._last_redis_ts:
                                    self._local_tokens = min(self.capacity, redis_tokens)
                                    self._local_last_refill = time.monotonic()
                                    self._last_redis_ts = redis_ts
                    else:
                        # Defensive: some clients may return scalar for
                        # legacy script versions or unexpected shapes.
                        try:
                            acquired = int(res) == 1
                        except (TypeError, ValueError):
                            acquired = bool(res)
                    self._warned_redis = False
                except Exception as exc:
                    # Chặn log spam (Review Patch #5)
                    if not self._warned_redis:
                        logger.warning(
                            "TokenBucket(%s): Redis error, falling back: %s",
                            self.provider, exc,
                        )
                        self._warned_redis = True
                    acquired = await self._acquire_local()
            else:
                acquired = await self._acquire_local()

            if acquired:
                return True

            elapsed = time.perf_counter() - start_time
            if elapsed >= timeout_s:
                # AC#7: emit a single throttle log on final give-up so the
                # event is observable in metrics/log aggregation.
                logger.info(
                    json.dumps({
                        "event": "rate_limited",
                        "provider": self.provider,
                        "wait_ms": int(elapsed * 1000),
                        "outcome": "timeout",
                    })
                )
                return False

            # Bucket empty AND refill rate cannot satisfy this request within
            # the budget — bail immediately so callers don't block uselessly.
            if unrefillable:
                logger.info(
                    json.dumps({
                        "event": "rate_limited",
                        "provider": self.provider,
                        "wait_ms": int(elapsed * 1000),
                        "outcome": "unrefillable",
                    })
                )
                return False

            # Dynamic wait step (Review Patch #7)
            # Wait at least 100ms or 1/refill_rate, but no more than 500ms.
            # Round-2 fix: previous `self.refill_rate or 1.0` masked refill=0
            # because `0.0 or 1.0 == 1.0`. Guard explicitly with `> 0`.
            if self.refill_rate > 0:
                wait_step = min(0.5, max(0.1, 1.0 / self.refill_rate))
            else:
                # refill_rate == 0 → bucket never refills; sleep until timeout.
                wait_step = max(0.0, timeout_s - elapsed)

            sleep_for = max(0.0, min(wait_step, timeout_s - elapsed))

            # AC#7: emit ONE throttle log on the first wait — operators care
            # that the request was throttled, not that we polled 50 times.
            if not first_wait_logged:
                logger.info(
                    json.dumps({
                        "event": "rate_limited",
                        "provider": self.provider,
                        "wait_ms": int(elapsed * 1000),
                        "outcome": "waiting",
                    })
                )
                first_wait_logged = True

            await asyncio.sleep(sleep_for)

    async def _acquire_local(self) -> bool:
        """In-memory fallback logic using monotonic time."""
        async with self._local_lock:
            now = time.monotonic()
            delta = max(0, now - self._local_last_refill)
            self._local_tokens = min(self.capacity, self._local_tokens + (delta * self.refill_rate))
            self._local_last_refill = now

            if self._local_tokens >= 1:
                self._local_tokens -= 1
                return True
            return False

    async def release(self, count: float = 1.0) -> None:
        """Return previously-acquired token(s) to the bucket.

        Story 11.7 / round-2 review of 11.4 — token-waste fix. When a tool
        raises an exception or times out AFTER `acquire()` succeeded, the
        outbound request was never made (or never received a 200), so the
        provider's quota wasn't actually charged. Returning the token avoids
        double-penalising our local quota.

        The release is best-effort: capped at capacity, atomic via Lua on
        Redis, lock-protected on the local fallback. Failures are logged but
        never raise — callers should not need to catch in their `except`.
        """
        # Atomic Lua: refill bucket by `count`, capped at capacity.
        redis = get_redis_client()
        if redis is not None:
            try:
                await redis.eval(_RELEASE_SCRIPT, 1, self.key, self.capacity, count)
                # Mirror the post-release state into the local fallback so a
                # subsequent Redis flap reflects the released token.
                async with self._local_lock:
                    self._local_tokens = min(self.capacity, self._local_tokens + count)
                return
            except Exception as exc:
                if not self._warned_redis:
                    logger.warning(
                        "TokenBucket(%s): Redis error on release, falling back: %s",
                        self.provider, exc,
                    )
                    self._warned_redis = True
                # Fall through to local-only release.

        # Local-only release path.
        async with self._local_lock:
            self._local_tokens = min(self.capacity, self._local_tokens + count)


# Singleton registry for easy access in decorator
_limiters: dict[str, TokenBucketRateLimiter] = {}


def get_limiter(provider: str) -> TokenBucketRateLimiter:
    """Get or create a limiter for the given provider (case-insensitive - Review Patch #2)."""
    p_lower = provider.lower()
    if p_lower not in _limiters:
        config = PROVIDER_RATE_LIMITS.get(p_lower, {"capacity": 60, "refill_rate": 1.0})
        _limiters[p_lower] = TokenBucketRateLimiter(
            provider=p_lower,
            capacity=config["capacity"],
            refill_rate=config["refill_rate"]
        )
    return _limiters[p_lower]


def _reset_limiters_for_tests() -> None:
    """Test helper: clear the singleton registry so tests can re-import with
    different env vars or limit configs without leaking state across cases."""
    _limiters.clear()
