import json
import logging
import time
from unittest.mock import AsyncMock, ANY, patch

import pytest

from app.agents.new_chat.middleware.circuit_breaker import (
    RedisCircuitBreaker,
    OPEN_COOLDOWN_SECONDS,
    PROBE_ALLOWED_TTL_SECONDS,
    STATE_KEY_TTL_SECONDS,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    redis.incr.return_value = 1
    redis.set.return_value = True
    redis.decr.return_value = 0
    return redis


@pytest.mark.asyncio
async def test_half_open_allows_only_one_probe(mock_redis):
    """AC1: OPEN expired → first request enters HALF_OPEN as probe (allowed),
    subsequent requests are blocked until probe resolves."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        source = "test_source"

        past_time = time.time() - 10

        # Call 1: state=open, open_until=past → SET NX creates probe slot,
        # transitions to half_open, DECR returns 0 (allowed).
        mock_redis.get.side_effect = [b"open", str(past_time).encode()]
        mock_redis.set.return_value = True  # SET NX succeeded
        mock_redis.decr.return_value = 0
        assert await cb.is_open(source) is False

        # Call 2: state=half_open, DECR returns -1 → blocked.
        mock_redis.get.side_effect = [b"half_open"]
        mock_redis.decr.return_value = -1
        assert await cb.is_open(source) is True


@pytest.mark.asyncio
async def test_setnx_atomicity_prevents_duplicate_probes(mock_redis):
    """AC1 (race): If SET NX returns False (another worker won the slot),
    state transition log is skipped — only one worker emits the open→half_open
    log line, ensuring single-probe semantics across workers."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        past_time = time.time() - 10

        # Worker B: SET NX returns False (worker A already created probe slot).
        mock_redis.get.side_effect = [b"open", str(past_time).encode()]
        mock_redis.set.return_value = False
        mock_redis.decr.return_value = -1  # probe was already consumed → blocked

        assert await cb.is_open("source_b") is True
        # Verify SET NX was called with nx=True and TTL.
        mock_redis.set.assert_any_call(
            "cb:probe_allowed:source_b",
            "1",
            nx=True,
            ex=PROBE_ALLOWED_TTL_SECONDS,
        )


@pytest.mark.asyncio
async def test_half_open_success_closes_circuit(mock_redis):
    """AC2: Probe success → CLOSE circuit and clear all keys."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        source = "test_source"
        mock_redis.get.return_value = b"half_open"

        await cb.record_success(source)

        mock_redis.set.assert_any_call(
            f"cb:state:{source}", "closed", ex=STATE_KEY_TTL_SECONDS
        )
        mock_redis.delete.assert_called_with(
            "cb:fail_count:test_source",
            "cb:open_until:test_source",
            "cb:state:test_source",
            "cb:probe_allowed:test_source",
        )


@pytest.mark.asyncio
async def test_half_open_failure_reopens_circuit(mock_redis):
    """AC3: Probe failure during HALF_OPEN → reopen circuit with fresh cooldown."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        source = "test_source"
        mock_redis.get.return_value = b"half_open"

        await cb.record_failure(source)

        mock_redis.set.assert_any_call(
            f"cb:open_until:{source}", ANY, ex=OPEN_COOLDOWN_SECONDS
        )
        mock_redis.set.assert_any_call(
            f"cb:state:{source}", "open", ex=STATE_KEY_TTL_SECONDS
        )


@pytest.mark.asyncio
async def test_record_failure_skips_when_already_open(mock_redis):
    """Race fix: if circuit is already OPEN with live cooldown, record_failure
    should be a no-op so worker B doesn't churn open_until set by worker A."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        mock_redis.get.return_value = b"open"

        await cb.record_failure("test_source")

        # incr / set / delete should NOT have been called.
        mock_redis.incr.assert_not_called()
        for call in mock_redis.set.call_args_list:
            args, _ = call
            assert "open_until" not in args[0]


@pytest.mark.asyncio
async def test_redis_down_returns_last_known_state(mock_redis):
    """AC4: Redis down → returns last-known state from in-memory cache."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        source = "test_source"

        # 1. Cache update success: CLOSED.
        mock_redis.get.return_value = None
        assert await cb.is_open(source) is False

        # 2. Redis down → returns False (last-known cache).
        mock_redis.get.side_effect = Exception("Redis connection lost")
        assert await cb.is_open(source) is False

        # 3. Simulate circuit OPEN successfully.
        future_time = time.time() + 10
        mock_redis.get.side_effect = [b"open", str(future_time).encode()]
        assert await cb.is_open(source) is True

        # 4. Redis down again → returns True (cache reflects last state).
        mock_redis.get.side_effect = Exception("Redis connection lost")
        assert await cb.is_open(source) is True


@pytest.mark.asyncio
async def test_state_change_log_is_json(mock_redis, caplog):
    """AC5: State transition log must be a structured JSON line, not just
    `extra=` fields that depend on a downstream JSON formatter."""
    with patch(
        "app.agents.new_chat.middleware.circuit_breaker.get_redis_client",
        return_value=mock_redis,
    ):
        cb = RedisCircuitBreaker()
        source = "test_source"
        mock_redis.get.return_value = b"half_open"

        with caplog.at_level(
            logging.INFO,
            logger="app.agents.new_chat.middleware.circuit_breaker",
        ):
            await cb.record_success(source)

        # Find the structured log message and verify it parses as JSON
        # with the required event fields.
        json_messages = []
        for record in caplog.records:
            try:
                obj = json.loads(record.getMessage())
                if obj.get("event") == "circuit_state_change":
                    json_messages.append(obj)
            except (ValueError, TypeError):
                continue

        assert json_messages, "expected at least one structured JSON state-change log line"
        msg = json_messages[0]
        assert msg["event"] == "circuit_state_change"
        assert msg["source"] == source
        assert msg["from"] == "half_open"
        assert msg["to"] == "closed"
