"""Integration test T8.2: Redis-backed ``run_event_bus`` cross-replica delivery.

Two ``RedisRunEventBus`` instances sharing the same Redis URL simulate two
worker processes. A publish from "replica B" must be visible to a subscriber
on "replica A" within the listener's polling window.

Requires a real Redis instance (``REDIS_APP_URL``). Skipped automatically when
Redis is unreachable so the rest of the suite remains hermetic.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.capabilities.core.events_redis import RedisRunEventBus
from app.config import config

pytestmark = [pytest.mark.integration]

_BUS_A: RedisRunEventBus | None = None
_BUS_B: RedisRunEventBus | None = None


async def _redis_available() -> bool:
    """Probe Redis once; cache the result for the session."""
    try:
        from redis import asyncio as aioredis

        client = aioredis.from_url(
            config.REDIS_APP_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        pong = await client.ping()
        await client.aclose()
        return bool(pong)
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def _skip_if_no_redis():
    if not await _redis_available():
        pytest.skip("Redis unavailable — skipping cross-replica bus test")


@pytest.fixture
async def bus_a():
    global _BUS_A
    _BUS_A = RedisRunEventBus(buffer_size=64, subscriber_queue_size=64)
    yield _BUS_A
    # Drain listener and close pubsub so the next test starts clean.
    # CancelledError inherits BaseException in 3.12, so suppress it explicitly.
    import contextlib

    with contextlib.suppress(Exception, asyncio.CancelledError):
        await _BUS_A._stop_listener()
    if _BUS_A._redis is not None:
        with contextlib.suppress(Exception):
            await _BUS_A._redis.aclose()
        _BUS_A._redis = None
    _BUS_A._buffers.clear()
    _BUS_A._subscribers.clear()


@pytest.fixture
async def bus_b():
    global _BUS_B
    _BUS_B = RedisRunEventBus(buffer_size=64, subscriber_queue_size=64)
    yield _BUS_B
    import contextlib

    with contextlib.suppress(Exception, asyncio.CancelledError):
        await _BUS_B._stop_listener()
    if _BUS_B._redis is not None:
        with contextlib.suppress(Exception):
            await _BUS_B._redis.aclose()
        _BUS_B._redis = None
    _BUS_B._buffers.clear()
    _BUS_B._subscribers.clear()


@pytest.mark.asyncio
async def test_cross_replica_publish_reaches_subscriber_on_other_bus(
    bus_a, bus_b
):
    """T8.2: publish from B, tail from A sees the event within 5s."""
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"

    # Subscribe on replica A first so the channel exists before publish.
    queue_a = bus_a.subscribe(run_id)
    # Give the listener a moment to register the Redis subscription.
    await asyncio.sleep(0.5)

    # Publish from replica B.
    event = {"type": "progress", "run_id": run_id, "phase": "research"}
    bus_b.publish(run_id, event)

    # Drain the listener task queue on A — the event must arrive via Redis.
    try:
        received = await asyncio.wait_for(queue_a.get(), timeout=5.0)
    except TimeoutError:
        pytest.fail("cross-replica event not delivered within 5s")

    assert received["type"] == "progress"
    assert received["run_id"] == run_id
    assert received["phase"] == "research"

    bus_a.unsubscribe(run_id, queue_a)
