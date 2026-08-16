"""Red-phase unit tests for Redis Lua Leaky-Bucket Rate Limiter per platform (Story 23.1 / AC-3).

Governed by:
- AC-3: Redis Lua Leaky-Bucket Rate Limiter & Circuit Breaker
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

# Target module to be implemented in Story 23.1:
# from app.lead_intelligence.services.rate_limiter import (
#     PlatformRateLimiter,
#     RateLimitResult,
#     PLATFORM_RATE_LIMITS,
#     RATE_LIMITER_LUA_SCRIPT,
# )

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Per-Platform Rate Limits Configuration (AC-3)
# ---------------------------------------------------------------------------
class TestPlatformRateLimitsConfig:
    """Validate per-platform rate limit specifications."""

    def test_platform_rate_limit_constants_match_ac3(self) -> None:
        """AC-3: Batdongsan (5), Chợ Tốt (10), TopCV (3), ITviec (3), Masothue (2)."""
        from app.lead_intelligence.services.rate_limiter import (
            PLATFORM_RATE_LIMITS,
        )

        assert PLATFORM_RATE_LIMITS["batdongsan"] == 5
        assert PLATFORM_RATE_LIMITS["chotot"] == 10
        assert PLATFORM_RATE_LIMITS["topcv"] == 3
        assert PLATFORM_RATE_LIMITS["itviec"] == 3
        assert PLATFORM_RATE_LIMITS["masothue"] == 2


# ---------------------------------------------------------------------------
# 2. Redis Lua Script Execution & Atomic Token Depletion (AC-3)
# ---------------------------------------------------------------------------
class TestRedisLuaRateLimiterExecution:
    """Validate Lua script execution for atomic leaky-bucket token checking."""

    @pytest.mark.asyncio
    async def test_acquire_calls_redis_lua_eval(self) -> None:
        """Acquiring a token executes the atomic Lua script in Redis."""
        from app.lead_intelligence.services.rate_limiter import (
            PlatformRateLimiter,
            RateLimitResult,
        )

        mock_redis = AsyncMock()
        # Lua script returns [1, 4.0, 0] -> [allowed (1/0), remaining_tokens, retry_after_ms]
        mock_redis.eval.return_value = [1, 4.0, 0]

        limiter = PlatformRateLimiter(redis_client=mock_redis)
        result = await limiter.acquire("batdongsan")

        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert result.remaining_tokens == 4.0
        assert result.retry_after_ms == 0

        mock_redis.eval.assert_called_once()
        call_args = mock_redis.eval.call_args
        # Key should be prefixed e.g. "rate_limit:scraper:batdongsan"
        assert "batdongsan" in str(call_args)

    @pytest.mark.asyncio
    async def test_acquire_blocks_when_bucket_is_exhausted(self) -> None:
        """When tokens are exhausted, Lua script returns allowed=0 with retry_after_ms > 0."""
        from app.lead_intelligence.services.rate_limiter import (
            PlatformRateLimiter,
        )

        mock_redis = AsyncMock()
        # Lua script returns [0, 0.0, 200] -> [allowed=0, remaining=0.0, retry_after_ms=200]
        mock_redis.eval.return_value = [0, 0.0, 200]

        limiter = PlatformRateLimiter(redis_client=mock_redis)
        result = await limiter.acquire("masothue")

        assert result.allowed is False
        assert result.retry_after_ms == 200
        assert result.remaining_tokens == 0.0

    @pytest.mark.asyncio
    async def test_acquire_with_custom_cost(self) -> None:
        """Bulk requests can consume multiple tokens atomically."""
        from app.lead_intelligence.services.rate_limiter import (
            PlatformRateLimiter,
        )

        mock_redis = AsyncMock()
        mock_redis.eval.return_value = [1, 1.0, 0]

        limiter = PlatformRateLimiter(redis_client=mock_redis)
        result = await limiter.acquire("chotot", cost=3)

        assert result.allowed is True
        mock_redis.eval.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Fallback & Unknown Platform Handling
# ---------------------------------------------------------------------------
class TestRateLimiterEdgeCases:
    """Validate behavior on unconfigured platforms or Redis transient errors."""

    @pytest.mark.asyncio
    async def test_unknown_platform_uses_conservative_default(self) -> None:
        """Unknown platform defaults to conservative 1 req/s."""
        from app.lead_intelligence.services.rate_limiter import (
            DEFAULT_FALLBACK_RATE_LIMIT,
            PlatformRateLimiter,
        )

        mock_redis = AsyncMock()
        mock_redis.eval.return_value = [1, 0.0, 0]

        limiter = PlatformRateLimiter(redis_client=mock_redis)
        result = await limiter.acquire("unregistered_vendor")

        assert result.allowed is True
        assert DEFAULT_FALLBACK_RATE_LIMIT <= 2
