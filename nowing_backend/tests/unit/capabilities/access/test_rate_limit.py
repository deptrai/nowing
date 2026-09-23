"""Per-workspace rate limit: a secondary guard behind the credit meter-gate (05)."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.capabilities.core.access import rate_limit


def _request(workspace_id: int) -> Request:
    return Request({"type": "http", "path_params": {"workspace_id": workspace_id}})


@pytest.mark.asyncio
async def test_passes_at_the_limit(monkeypatch):
    monkeypatch.setattr(
        rate_limit, "_incr", lambda *a, **k: rate_limit.CAPABILITY_RATE_LIMIT_PER_MINUTE
    )
    await rate_limit.enforce_capability_rate_limit(_request(1))


@pytest.mark.asyncio
async def test_blocks_over_the_limit(monkeypatch):
    monkeypatch.setattr(
        rate_limit,
        "_incr",
        lambda *a, **k: rate_limit.CAPABILITY_RATE_LIMIT_PER_MINUTE + 1,
    )
    with pytest.raises(HTTPException) as exc:
        await rate_limit.enforce_capability_rate_limit(_request(1))
    assert exc.value.status_code == 429


def test_memory_fallback_counts_within_window():
    rate_limit._memory.clear()
    assert rate_limit._incr_memory("k", window_seconds=60) == 1
    assert rate_limit._incr_memory("k", window_seconds=60) == 2


def test_incr_redis_failure_falls_back_to_scaled_memory(monkeypatch):
    """Item 2: When Redis is down, memory counter is scaled by CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR."""
    rate_limit._memory.clear()
    # Force Redis client failure
    monkeypatch.setattr(
        rate_limit,
        "_redis_client",
        lambda: (_ for _ in ()).throw(ConnectionError("Redis connection refused")),
    )

    # First hit returns 1 * DIVISOR = 4
    count1 = rate_limit._incr("test-workspace", window_seconds=60)
    assert count1 == 1 * rate_limit.CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR

    # Second hit returns 2 * DIVISOR = 8
    count2 = rate_limit._incr("test-workspace", window_seconds=60)
    assert count2 == 2 * rate_limit.CAPABILITY_RATE_LIMIT_FALLBACK_DIVISOR

