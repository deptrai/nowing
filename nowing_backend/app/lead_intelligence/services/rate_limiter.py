"""Redis Lua Leaky-Bucket Rate Limiter per platform (Story 23.1 / AC-3).

Governed by:
- AC-3: Redis Lua Leaky-Bucket Rate Limiter (Batdongsan 5 req/s, Chợ Tốt 10 req/s, TopCV 3 req/s, Masothue 2 req/s)
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

PLATFORM_RATE_LIMITS: dict[str, int] = {
    "batdongsan": 5,
    "chotot": 10,
    "topcv": 3,
    "itviec": 3,
    "masothue": 2,
}

DEFAULT_FALLBACK_RATE_LIMIT: int = 1

RATE_LIMITER_LUA_SCRIPT = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])

if rate == nil or rate <= 0 then
    return {1, capacity, 0}
end

-- Fetch monotonic Redis server time to prevent multi-node clock drift
local time_arr = redis.call('TIME')
local now = (tonumber(time_arr[1]) * 1000) + math.floor(tonumber(time_arr[2]) / 1000)

local data = redis.call('HMGET', key, 'tokens', 'last_update')
local tokens = tonumber(data[1])
local last_update = tonumber(data[2])

if tokens == nil or last_update == nil then
    tokens = capacity
    last_update = now
else
    local delta = math.max(0, now - last_update) / 1000.0
    tokens = math.min(capacity, tokens + (delta * rate))
    last_update = now
end

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HSET', key, 'tokens', tokens, 'last_update', last_update)
    redis.call('EXPIRE', key, 60)
    return {1, tokens, 0}
else
    local needed = cost - tokens
    local retry_after_ms = math.ceil((needed / rate) * 1000.0)
    redis.call('HSET', key, 'tokens', tokens, 'last_update', last_update)
    redis.call('EXPIRE', key, 60)
    return {0, tokens, retry_after_ms}
end
"""


class RateLimitResult(BaseModel):
    """Result of rate limit check."""

    allowed: bool
    remaining_tokens: float
    retry_after_ms: int


class PlatformRateLimiter:
    """Per-platform rate limiter enforcing leak-bucket token rates in Redis."""

    def __init__(self, redis_client: Any = None) -> None:
        self._redis = redis_client
        self._lua_sha: str | None = None

    async def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        return await get_redis_client()

    async def acquire(self, platform: str, cost: int = 1) -> RateLimitResult:
        """
        Attempt to acquire `cost` tokens for given platform.
        Returns RateLimitResult with allowed status and remaining tokens.
        """
        redis = await self._get_redis()
        normalized_platform = platform.strip().lower()
        rate = PLATFORM_RATE_LIMITS.get(
            normalized_platform, DEFAULT_FALLBACK_RATE_LIMIT
        )
        capacity = max(rate, cost)
        key = f"rate_limit:scraper:{normalized_platform}"

        try:
            res = await redis.eval(
                RATE_LIMITER_LUA_SCRIPT,
                1,
                key,
                rate,
                capacity,
                cost,
            )
            # Response: [allowed_int, remaining_tokens, retry_after_ms]
            allowed = bool(res[0])
            remaining = float(res[1])
            retry_after_ms = int(res[2])

            return RateLimitResult(
                allowed=allowed,
                remaining_tokens=remaining,
                retry_after_ms=retry_after_ms,
            )
        except Exception as exc:
            logger.warning(
                "Redis Lua rate limiter failed for %s: %s, allowing request",
                platform,
                exc,
            )
            return RateLimitResult(
                allowed=True,
                remaining_tokens=float(rate),
                retry_after_ms=0,
            )
