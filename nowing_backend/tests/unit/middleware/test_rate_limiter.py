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
    """Verify Redis EVAL is invoked and Lua return [1, tokens, last_refill] is success."""
    mock_redis = AsyncMock()
    # Story 11.6 / ADR-011: Lua now returns [acquired, tokens, last_refill]
    mock_redis.eval.return_value = [1, "9.0", "1234567890.123"]

    limiter = TokenBucketRateLimiter(provider="redis_test", capacity=10, refill_rate=1.0)
    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        assert await limiter.acquire(timeout_s=0.1) is True
        assert mock_redis.eval.called


@pytest.mark.asyncio
async def test_redis_eval_returns_legacy_int_still_works():
    """Defensive: if Lua somehow returns a scalar (legacy script, unexpected
    deployment), the limiter still works."""
    mock_redis = AsyncMock()
    mock_redis.eval.return_value = b"1"

    limiter = TokenBucketRateLimiter(provider="bytes_redis", capacity=10, refill_rate=1.0)
    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        assert await limiter.acquire(timeout_s=0.1) is True


@pytest.mark.asyncio
async def test_ac4_concurrent_mirror_writes_use_redis_ts_ordering():
    """Story 11.6 round 2: when two concurrent acquires complete EVAL out of
    order (B's response with `last_refill=t1` lands before A's stale
    `last_refill=t0`), the older response must NOT clobber the fresher mirror.
    Otherwise local would carry a stale-too-high token count and reintroduce
    a smaller version of the double-consume bug ADR-011 was meant to close.
    """
    limiter = TokenBucketRateLimiter(provider="toctou", capacity=10, refill_rate=0.0)

    # Manually exercise both mirror writes in deliberate-stale order.
    # Newer response (smaller tokens, larger ts) lands first.
    async def apply_mirror(redis_tokens: float, redis_ts: float) -> None:
        async with limiter._local_lock:
            if redis_ts >= limiter._last_redis_ts:
                limiter._local_tokens = min(limiter.capacity, redis_tokens)
                limiter._local_last_refill = time.monotonic()
                limiter._last_redis_ts = redis_ts

    # Worker B's fresh response: tokens=1.0, ts=1001
    await apply_mirror(1.0, 1001.0)
    # Worker A's STALE response: tokens=2.0, ts=1000 (arrives later)
    await apply_mirror(2.0, 1000.0)

    # Local must reflect the fresher write, not the stale one.
    assert limiter._local_tokens == 1.0, (
        f"stale mirror clobbered fresh state: got {limiter._local_tokens}, expected 1.0"
    )


@pytest.mark.asyncio
async def test_ac4_redis_flap_no_double_consume():
    """Story 11.6 / ADR-011: when Redis flaps mid-acquire, total tokens
    consumed across Redis + local must NOT exceed the bucket capacity.

    Setup: capacity=3, refill_rate=0. Redis succeeds twice (consume 2),
    then goes down. The local mirror should reflect the post-EVAL state
    (1 token left), so subsequent Redis-down acquires drain from `1`,
    not from `3` (which would be the stale "fresh capacity" bug).
    """
    state = {"calls": 0}

    async def flaky_eval(*_args, **_kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            # Redis up: consumed 1, tokens left = 2
            return [1, "2.0", "1000.0"]
        if state["calls"] == 2:
            # Redis up: consumed 1, tokens left = 1
            return [1, "1.0", "1001.0"]
        # Redis down from call 3 onward
        raise RuntimeError("Redis connection lost")

    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = flaky_eval

    limiter = TokenBucketRateLimiter(provider="flap_test", capacity=3, refill_rate=0.0)

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        # Phase 1: Redis up — 2 acquires succeed, local mirror tracks Redis.
        assert await limiter.acquire(timeout_s=0.1) is True
        assert await limiter.acquire(timeout_s=0.1) is True

        # After 2 successful Redis EVALs, local mirror should hold 1 token.
        # Without the state-mirror fix, _local_tokens would still be `capacity`
        # (3) — leaving room for 3 more local consumes = 5 total (over capacity).
        assert limiter._local_tokens <= 1.0, (
            f"local mirror should reflect Redis state (~1 token), "
            f"got {limiter._local_tokens}"
        )

        # Phase 2: Redis down — local fallback drains from mirrored state,
        # not from a stale `capacity` reset.
        assert await limiter.acquire(timeout_s=0.1) is True  # consume 3rd
        # Bucket should now be empty across BOTH stores.
        assert await limiter.acquire(timeout_s=0.1) is False  # 4th rejected


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


# ---------------------------------------------------------------------------
# Story 11.7 T1 — release() API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_returns_token_to_local_bucket():
    """Story 11.7 T1: release() must add a token back when called without Redis."""
    limiter = TokenBucketRateLimiter(provider="rel_local", capacity=3, refill_rate=0.0)

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ):
        # Drain to 0
        for _ in range(3):
            assert await limiter.acquire(timeout_s=0.05) is True
        assert limiter._local_tokens < 1.0

        # Release returns it
        await limiter.release()
        assert limiter._local_tokens >= 1.0

        # Subsequent acquire succeeds (proves the released token is real)
        assert await limiter.acquire(timeout_s=0.05) is True


@pytest.mark.asyncio
async def test_release_capped_at_capacity():
    """Releases beyond capacity must clamp — no infinite token store."""
    limiter = TokenBucketRateLimiter(provider="rel_cap", capacity=2, refill_rate=0.0)

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=None,
    ):
        # Bucket starts at capacity. Release more.
        await limiter.release(count=5.0)
        assert limiter._local_tokens == 2.0  # clamped


@pytest.mark.asyncio
async def test_release_via_redis_lua_path():
    """When Redis is up, release() runs the atomic Lua script and mirrors locally."""
    mock_redis = AsyncMock()
    mock_redis.eval.return_value = "3.0"  # post-release token count from Lua

    limiter = TokenBucketRateLimiter(provider="rel_redis", capacity=10, refill_rate=0.0)
    # Simulate prior drain
    limiter._local_tokens = 2.0

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        await limiter.release(count=1.0)

        # Redis Lua was called
        mock_redis.eval.assert_called_once()
        # Local mirror reflects the +1
        assert limiter._local_tokens == 3.0


@pytest.mark.asyncio
async def test_release_swallows_redis_errors():
    """release() must NOT raise even if Redis is broken — callers in finally
    blocks should not have to wrap it."""
    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = RuntimeError("Redis connection lost")

    limiter = TokenBucketRateLimiter(provider="rel_err", capacity=5, refill_rate=0.0)
    limiter._local_tokens = 1.0

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_redis_client",
        return_value=mock_redis,
    ):
        # Should not raise.
        await limiter.release(count=1.0)
        # Local fallback still applied.
        assert limiter._local_tokens == 2.0


def test_get_limiter_is_case_insensitive():
    a = get_limiter("CoinGecko")
    b = get_limiter("coingecko")
    assert a is b
