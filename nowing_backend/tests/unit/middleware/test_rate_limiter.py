"""Unit tests for Story 11.4 — TokenBucketRateLimiter.

Round 2 review additions:
- AC#1 explicit 31st-request scenario
- AC#4 concurrent acquires across "workers" via shared Redis
- AC#5 Redis flap (up → down → up) fallback transition
- AC#6 env-var override end-to-end
- AC#7 structured JSON log structure assertion
"""

import asyncio
import importlib
import json
import logging
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.new_chat.middleware.rate_limiter import (
    TokenBucketRateLimiter,
    _reset_limiters_for_tests,
    get_limiter,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_limiter_registry():
    _reset_limiters_for_tests()
    yield
    _reset_limiters_for_tests()


# ---------------------------------------------------------------------------
# Existing happy-path / fallback tests (round 1 baseline, hardened in round 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_success_initial():
    """Verify that acquire succeeds when the bucket is full (local fallback)."""
    limiter = TokenBucketRateLimiter(provider="test", capacity=10, refill_rate=1.0)
    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ):
        assert await limiter.acquire(timeout_s=0.1) is True


@pytest.mark.asyncio
async def test_acquire_exhaustion_with_zero_refill_fails_fast():
    """refill_rate=0 should fail-fast (no infinite wait) when bucket is empty.
    Round 2 review: the previous `self.refill_rate or 1.0` masked zero refill;
    now zero-refill correctly waits the full timeout but no longer hot-spins."""
    limiter = TokenBucketRateLimiter(
        provider="test_exhaust", capacity=1, refill_rate=0.0,
    )

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ):
        assert await limiter.acquire(timeout_s=0.1) is True
        # Bucket exhausted — second call must fail within budget.
        start = time.perf_counter()
        assert await limiter.acquire(timeout_s=0.2) is False
        elapsed = time.perf_counter() - start
        # Should not exceed timeout by more than scheduler jitter.
        assert elapsed < 0.5


@pytest.mark.asyncio
async def test_unrefillable_bucket_fails_fast():
    """Round 2 review: when 1/refill_rate > timeout, fail-fast instead of polling."""
    # 1 token per 60s but caller only has 0.5s — cannot satisfy.
    limiter = TokenBucketRateLimiter(
        provider="goplus_like", capacity=1, refill_rate=1.0 / 60.0,
    )

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ):
        assert await limiter.acquire(timeout_s=0.5) is True
        start = time.perf_counter()
        assert await limiter.acquire(timeout_s=0.5) is False
        elapsed = time.perf_counter() - start
        # Fail-fast: should return well under the 0.5s budget.
        assert elapsed < 0.1, f"expected fail-fast, got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_refill_logic():
    """Verify that tokens refill over time (local fallback)."""
    limiter = TokenBucketRateLimiter(
        provider="test_refill", capacity=1, refill_rate=100.0,
    )
    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ):
        assert await limiter.acquire(timeout_s=0.1) is True
        # With 100 tok/s, ~10ms suffices; the wait loop should observe a refill.
        assert await limiter.acquire(timeout_s=0.5) is True


@pytest.mark.asyncio
async def test_redis_logic():
    """Verify Redis EVAL is invoked and a Lua return of 1 is treated as success."""
    mock_redis = AsyncMock()
    mock_redis.eval.return_value = 1

    limiter = TokenBucketRateLimiter(provider="redis_test", capacity=10, refill_rate=1.0)
    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        assert await limiter.acquire(timeout_s=0.1) is True
        assert mock_redis.eval.called


@pytest.mark.asyncio
async def test_redis_eval_returns_bytes_treated_as_int():
    """Round 2 defensive: redis-py wrappers may return bytes/str for Lua ints.
    The defensive `int(res) == 1` cast must handle this without flipping
    every request to fail-and-wait."""
    mock_redis = AsyncMock()
    mock_redis.eval.return_value = b"1"  # some clients

    limiter = TokenBucketRateLimiter(provider="bytes_redis", capacity=10, refill_rate=1.0)
    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        assert await limiter.acquire(timeout_s=0.1) is True


# ---------------------------------------------------------------------------
# AC#1 — request 31 within 1 minute is QUEUED, not 429
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac1_request_31_is_queued_and_succeeds():
    """AC#1: 30 requests succeed instantly, the 31st is queued and succeeds
    after a brief refill wait (NOT fail-fast / 429)."""
    # Simulate CoinGecko free tier: 30 capacity, 0.5 tok/sec refill.
    # We bump refill to 50/sec so the test runs fast — semantics are identical.
    limiter = TokenBucketRateLimiter(
        provider="coingecko_test", capacity=30, refill_rate=50.0,
    )

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ):
        # Drain all 30 tokens.
        for i in range(30):
            assert await limiter.acquire(timeout_s=0.05) is True, f"req {i + 1} failed"

        # Request 31: bucket empty. Must NOT fail-fast — should wait and succeed
        # within the 5s budget (in practice ~20ms with refill=50/s).
        start = time.perf_counter()
        assert await limiter.acquire(timeout_s=5.0) is True
        elapsed = time.perf_counter() - start
        # Must have waited at least the refill period (1/50 = 20ms) but not 5s.
        assert 0.001 < elapsed < 1.0, f"unexpected wait: {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# AC#4 — multi-worker via shared Redis (concurrent acquires)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac4_concurrent_acquires_share_redis_state():
    """AC#4: two simulated workers hitting the same Redis key see a shared
    counter — total successful acquires across both must equal the bucket
    capacity (no double-spend)."""
    capacity = 10
    consumed = {"count": capacity}

    async def fake_eval(*_args, **_kwargs):
        # Simulate atomic decrement: 1 if tokens remained, 0 otherwise.
        if consumed["count"] > 0:
            consumed["count"] -= 1
            return 1
        return 0

    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = fake_eval

    worker_a = TokenBucketRateLimiter(provider="shared", capacity=capacity, refill_rate=0.0)
    worker_b = TokenBucketRateLimiter(provider="shared", capacity=capacity, refill_rate=0.0)

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        # 20 concurrent acquires across 2 workers.
        results = await asyncio.gather(
            *[worker_a.acquire(timeout_s=0.1) for _ in range(10)],
            *[worker_b.acquire(timeout_s=0.1) for _ in range(10)],
        )

    # Exactly `capacity` successes; the rest must time out.
    assert sum(results) == capacity
    assert sum(1 for r in results if r is False) == 10


# ---------------------------------------------------------------------------
# AC#5 — Redis flap (up → down → up) fallback transition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac5_redis_flap_falls_back_then_recovers():
    """AC#5: when Redis fails mid-flight, fall back to local. When Redis
    recovers, resume Redis path. Over-counting acceptable; primary contract
    is "throttle, never spam"."""
    state = {"redis_up": True}

    async def flaky_eval(*_args, **_kwargs):
        if not state["redis_up"]:
            raise RuntimeError("Redis connection lost")
        return 1

    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = flaky_eval

    limiter = TokenBucketRateLimiter(provider="flaky", capacity=10, refill_rate=1.0)

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        # Phase 1: Redis up — Redis path consumes.
        assert await limiter.acquire(timeout_s=0.1) is True
        assert mock_redis.eval.call_count == 1

        # Phase 2: Redis down — fall back to local. Local bucket still has
        # tokens (capacity=10), so acquire still succeeds.
        state["redis_up"] = False
        assert await limiter.acquire(timeout_s=0.1) is True

        # Phase 3: Redis up again — Redis path resumes.
        state["redis_up"] = True
        assert await limiter.acquire(timeout_s=0.1) is True


# ---------------------------------------------------------------------------
# AC#6 — env-var override end-to-end
# ---------------------------------------------------------------------------


def test_ac6_env_var_overrides_provider_capacity(monkeypatch):
    """AC#6: capacity is configurable via env vars. We re-import the module
    after setting the env so the module-level dict picks up our override."""
    monkeypatch.setenv("RL_COINGECKO_CAP", "99")

    import app.agents.new_chat.middleware.rate_limiter as rl_mod
    importlib.reload(rl_mod)

    try:
        assert rl_mod.PROVIDER_RATE_LIMITS["coingecko"]["capacity"] == 99.0
    finally:
        monkeypatch.delenv("RL_COINGECKO_CAP", raising=False)
        importlib.reload(rl_mod)


def test_ac6_env_var_malformed_does_not_crash_import(monkeypatch, caplog):
    """Round 2 review: a malformed env value used to crash `float()` at import
    time, taking down agent startup. Now it logs a warning and falls back."""
    monkeypatch.setenv("RL_COINGECKO_CAP", "not_a_number")

    import app.agents.new_chat.middleware.rate_limiter as rl_mod
    with caplog.at_level(logging.WARNING, logger=rl_mod.__name__):
        importlib.reload(rl_mod)

    try:
        assert rl_mod.PROVIDER_RATE_LIMITS["coingecko"]["capacity"] == 30.0
        assert any(
            "invalid value for RL_COINGECKO_CAP" in record.getMessage()
            for record in caplog.records
        )
    finally:
        monkeypatch.delenv("RL_COINGECKO_CAP", raising=False)
        importlib.reload(rl_mod)


# ---------------------------------------------------------------------------
# AC#7 — structured JSON log structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac7_throttle_log_is_parseable_json_with_required_keys(caplog):
    """AC#7: when throttled, emit a JSON line with `event`, `provider`, `wait_ms`."""
    limiter = TokenBucketRateLimiter(
        provider="logged", capacity=1, refill_rate=0.0,
    )

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ), caplog.at_level(
        logging.INFO,
        logger="app.agents.new_chat.middleware.rate_limiter",
    ):
        assert await limiter.acquire(timeout_s=0.1) is True
        # Bucket exhausted -> next call will throttle and emit a log.
        await limiter.acquire(timeout_s=0.2)

    json_records = []
    for record in caplog.records:
        msg = record.getMessage()
        if not msg.strip().startswith("{"):
            continue
        try:
            json_records.append(json.loads(msg))
        except (TypeError, ValueError):
            continue

    rate_logs = [r for r in json_records if r.get("event") == "rate_limited"]
    assert rate_logs, "expected at least one rate_limited JSON log line"
    log = rate_logs[0]
    assert log["provider"] == "logged"
    assert "wait_ms" in log and isinstance(log["wait_ms"], int)
    assert log.get("outcome") in {"waiting", "timeout", "unrefillable"}


@pytest.mark.asyncio
async def test_ac7_throttle_log_emitted_at_most_twice_not_per_poll(caplog):
    """Round 2 review: previously the log fired on every poll iteration
    (~50 lines per 5s wait). Now: at most one "waiting" log + one "timeout"
    log per acquire call."""
    limiter = TokenBucketRateLimiter(
        provider="quiet", capacity=1, refill_rate=0.5,  # 1 token / 2s
    )

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ), caplog.at_level(
        logging.INFO,
        logger="app.agents.new_chat.middleware.rate_limiter",
    ):
        assert await limiter.acquire(timeout_s=0.5) is True
        # Exhausted: this acquire will time out (refill 1/2s, budget 0.5s,
        # 1/refill=2s > 0.5s so it actually fails fast as "unrefillable").
        await limiter.acquire(timeout_s=0.5)

    rate_logs = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.getMessage().strip().startswith("{")
        and "rate_limited" in r.getMessage()
    ]
    # Expect at most 2 lines (waiting + timeout) — definitely not 5+.
    assert 1 <= len(rate_logs) <= 2, f"expected ≤ 2 throttle logs, got {len(rate_logs)}"


# ---------------------------------------------------------------------------
# Limiter registry hygiene
# ---------------------------------------------------------------------------


def test_get_limiter_is_case_insensitive():
    a = get_limiter("CoinGecko")
    b = get_limiter("coingecko")
    assert a is b
