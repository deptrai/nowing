"""Red-phase unit tests for Scraper Platform Circuit Breaker (Story 23.1 / AC-3 & INV-23.3).

Governed by:
- AC-3: 3 Consecutive 429/CAPTCHA Anti-Bot Blocks Trip Circuit for 10 Minutes
- INV-23.3: Circuit Breaker Persistence in Redis (circuit_breaker:scraper:{platform}, TTL 600s)
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

# Target module to be implemented in Story 23.1:
# from app.lead_intelligence.services.circuit_breaker import (
#     PlatformCircuitBreaker,
#     CircuitState,
#     CIRCUIT_FAILURE_THRESHOLD,
#     CIRCUIT_COOLDOWN_SECONDS,
# )

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Circuit Breaker Invariants & Constants (INV-23.3 & AC-3)
# ---------------------------------------------------------------------------
class TestCircuitBreakerConstants:
    """Validate threshold and cooldown duration constants."""

    def test_constants_match_inv23_3(self) -> None:
        """Threshold must be 3 strikes; cooldown must be 600s (10 minutes)."""
        from app.lead_intelligence.services.circuit_breaker import (
            CIRCUIT_COOLDOWN_SECONDS,
            CIRCUIT_FAILURE_THRESHOLD,
        )

        assert CIRCUIT_FAILURE_THRESHOLD == 3
        assert CIRCUIT_COOLDOWN_SECONDS == 600


# ---------------------------------------------------------------------------
# 2. Strike Escalation & Trip Execution (AC-3)
# ---------------------------------------------------------------------------
class TestCircuitBreakerTripping:
    """Validate that 3 consecutive anti-bot blocks trip the platform circuit."""

    @pytest.mark.asyncio
    async def test_initial_state_is_available(self) -> None:
        """New or unblocked platform should report available (CLOSED state)."""
        from app.lead_intelligence.services.circuit_breaker import (
            PlatformCircuitBreaker,
        )

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No circuit breaker key in Redis

        breaker = PlatformCircuitBreaker(redis_client=mock_redis)
        is_available = await breaker.is_available("batdongsan")

        assert is_available is True
        mock_redis.get.assert_called_with("circuit_breaker:scraper:batdongsan")

    @pytest.mark.asyncio
    async def test_three_consecutive_failures_trips_circuit(self) -> None:
        """3 consecutive 429/antibot failures trip the circuit and set Redis key with 600s TTL."""
        from app.lead_intelligence.services.circuit_breaker import (
            PlatformCircuitBreaker,
        )

        mock_redis = AsyncMock()
        # Mock counter increment returning 1, 2, then 3
        mock_redis.incr.side_effect = [1, 2, 3]

        breaker = PlatformCircuitBreaker(redis_client=mock_redis)

        # Strike 1
        tripped_1 = await breaker.record_failure(
            platform="batdongsan",
            reason="HTTP 429 Too Many Requests",
            status_code=429,
        )
        assert tripped_1 is False

        # Strike 2
        tripped_2 = await breaker.record_failure(
            platform="batdongsan",
            reason="Cloudflare CAPTCHA Challenge",
            status_code=403,
        )
        assert tripped_2 is False

        # Strike 3 -> Tripped!
        tripped_3 = await breaker.record_failure(
            platform="batdongsan",
            reason="Cloudflare Block",
            status_code=403,
        )
        assert tripped_3 is True

        # Verify Redis key set with 600s TTL (INV-23.3)
        mock_redis.set.assert_called_with(
            "circuit_breaker:scraper:batdongsan",
            "OPEN",
            ex=600,
        )

    @pytest.mark.asyncio
    async def test_success_resets_failure_counter(self) -> None:
        """A successful scrape resets the failure streak before tripping."""
        from app.lead_intelligence.services.circuit_breaker import (
            PlatformCircuitBreaker,
        )

        mock_redis = AsyncMock()
        breaker = PlatformCircuitBreaker(redis_client=mock_redis)

        await breaker.record_success("batdongsan")
        mock_redis.delete.assert_called_with("circuit_breaker:failures:batdongsan")


# ---------------------------------------------------------------------------
# 3. Platform Isolation (AC-3)
# ---------------------------------------------------------------------------
class TestPlatformIsolation:
    """Validate that tripping one platform does not affect other scrapers."""

    @pytest.mark.asyncio
    async def test_tripped_platform_does_not_block_other_platforms(self) -> None:
        """When Batdongsan is tripped (OPEN), Chợ Tốt remains available (CLOSED)."""
        from app.lead_intelligence.services.circuit_breaker import (
            PlatformCircuitBreaker,
        )

        mock_redis = AsyncMock()

        async def mock_redis_get(key: str) -> bytes | None:
            if "batdongsan" in key:
                return b"OPEN"
            return None

        mock_redis.get.side_effect = mock_redis_get

        breaker = PlatformCircuitBreaker(redis_client=mock_redis)

        bds_available = await breaker.is_available("batdongsan")
        chotot_available = await breaker.is_available("chotot")
        masothue_available = await breaker.is_available("masothue")

        assert bds_available is False
        assert chotot_available is True
        assert masothue_available is True
