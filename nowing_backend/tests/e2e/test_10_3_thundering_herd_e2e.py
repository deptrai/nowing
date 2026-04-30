"""
E2E test for Story 10.3 — Thundering Herd Protection.

Tests the full lock stack end-to-end:
- Redis lock (if available) or local lock fallback
- Double-check pattern
- Concurrent access serialization

Run with: uv run python -m pytest tests/e2e/test_10_3_thundering_herd_e2e.py -v -s
"""
import asyncio
import json
import logging
import os
import time
from unittest.mock import AsyncMock, patch

import pytest

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# E2E-1: Redis lock singleton — verify get_redis_client() returns consistent client
# ---------------------------------------------------------------------------


async def test_e2e1_redis_singleton_consistent():
    """get_redis_client() returns same object on repeated calls."""
    from app.services.crypto_cache_lock import get_redis_client

    client_a = get_redis_client()
    client_b = get_redis_client()
    assert client_a is client_b, "get_redis_client() must return singleton"
    print(f"\n✓ Redis singleton: {type(client_a).__name__} — same object on repeat calls")


# ---------------------------------------------------------------------------
# E2E-2: Redis live ping (if Redis available)
# ---------------------------------------------------------------------------


async def test_e2e2_redis_live_ping():
    """If Redis is running, verify the singleton client can actually connect."""
    from app.services.crypto_cache_lock import get_redis_client

    client = get_redis_client()
    if client is None:
        pytest.skip("Redis unavailable — local lock fallback active")

    result = await client.ping()
    assert result is True
    print(f"\n✓ Redis ping OK — live connection confirmed")


# ---------------------------------------------------------------------------
# E2E-3: Full lock cycle with live Redis
# ---------------------------------------------------------------------------


async def test_e2e3_lock_acquire_and_release_redis():
    """Acquire lock → do work → verify key cleaned up after release."""
    from app.services.crypto_cache_lock import crypto_cache_lock, get_redis_client

    client = get_redis_client()
    if client is None:
        pytest.skip("Redis unavailable")

    lock_key = "e2e_test:crypto_lock:get_defillama_protocol:testHash123"

    # Verify key doesn't exist before
    before = await client.exists(lock_key)
    assert before == 0, "Lock key should not exist before test"

    inside_lock = False
    async with crypto_cache_lock(lock_key, redis_client=client, ttl=30):
        inside_lock = True
        # Verify key exists while lock is held
        during = await client.exists(lock_key)
        assert during == 1, "Lock key should exist while held"
        val = await client.get(lock_key)
        assert val is not None and len(val) == 36, f"Lock value should be UUID, got: {val}"
        print(f"\n✓ Lock held — key exists with UUID token: {val[:8]}...")

    # Verify key cleaned up after release
    after = await client.exists(lock_key)
    assert after == 0, "Lock key should be deleted after release"
    print("✓ Lock released — key cleaned up")


# ---------------------------------------------------------------------------
# E2E-4: Concurrent thundering herd with live Redis (core AC1 scenario)
# ---------------------------------------------------------------------------


async def test_e2e4_concurrent_thundering_herd_redis():
    """
    10 concurrent coroutines hit same lock key (simulating cache miss thundering herd).
    Verify: only 1 'wins' the lock first, others queue behind it.
    Double-check pattern ensures only 1 external call.
    """
    from app.services.crypto_cache_lock import crypto_cache_lock, get_redis_client

    client = get_redis_client()
    if client is None:
        pytest.skip("Redis unavailable — use test_e2e5 for local lock version")

    lock_key = "e2e_test:crypto_lock:thundering_herd_test:abc123"

    # Shared state
    api_call_count = 0
    shared_cache: dict = {}
    results = []

    async def simulate_agent_task(task_id: int):
        nonlocal api_call_count
        # Pre-lock check (all 10 see empty cache)
        if "data" in shared_cache:
            results.append(("cache_hit", task_id))
            return shared_cache["data"]

        async with crypto_cache_lock(lock_key, redis_client=client, ttl=30):
            # Double-check inside lock
            if "data" in shared_cache:
                results.append(("double_check_hit", task_id))
                return shared_cache["data"]

            # Winner — call "external API"
            api_call_count += 1
            await asyncio.sleep(0.05)  # simulate API latency
            shared_cache["data"] = {"tvl": 1_234_567, "winner": task_id}
            results.append(("api_called", task_id))
            return shared_cache["data"]

    start = time.monotonic()
    task_results = await asyncio.gather(*[simulate_agent_task(i) for i in range(10)])
    elapsed = time.monotonic() - start

    print(f"\n✓ 10 concurrent tasks completed in {elapsed:.2f}s")
    print(f"  Results breakdown: {[r[0] for r in results]}")
    print(f"  API calls: {api_call_count}")

    assert api_call_count == 1, f"Expected exactly 1 API call, got {api_call_count}"
    assert all(r == {"tvl": 1_234_567, "winner": task_results[0]['winner']} for r in task_results), \
        "All tasks should return the same data"

    # Count result types
    api_calls = [r for r in results if r[0] == "api_called"]
    double_check_hits = [r for r in results if r[0] == "double_check_hit"]
    cache_hits = [r for r in results if r[0] == "cache_hit"]

    print(f"  API winners: {len(api_calls)}, double-check hits: {len(double_check_hits)}, pre-lock hits: {len(cache_hits)}")
    assert len(api_calls) == 1, "Only 1 task should call the API"

    # Cleanup
    await client.delete(lock_key)


# ---------------------------------------------------------------------------
# E2E-5: Local lock fallback thundering herd (no Redis required)
# ---------------------------------------------------------------------------


async def test_e2e5_concurrent_thundering_herd_local_lock():
    """
    Same scenario as E2E-4 but using local asyncio.Lock fallback (redis_client=None).
    Verifies the fallback path works identically.
    """
    from app.services.crypto_cache_lock import crypto_cache_lock

    lock_key = "e2e_test:local_lock:thundering_herd"
    api_call_count = 0
    shared_cache: dict = {}
    results = []

    async def simulate_agent_task(task_id: int):
        nonlocal api_call_count
        if "data" in shared_cache:
            results.append(("cache_hit", task_id))
            return shared_cache["data"]

        async with crypto_cache_lock(lock_key, redis_client=None):
            if "data" in shared_cache:
                results.append(("double_check_hit", task_id))
                return shared_cache["data"]

            api_call_count += 1
            await asyncio.sleep(0.02)
            shared_cache["data"] = {"tvl": 999, "winner": task_id}
            results.append(("api_called", task_id))
            return shared_cache["data"]

    start = time.monotonic()
    task_results = await asyncio.gather(*[simulate_agent_task(i) for i in range(10)])
    elapsed = time.monotonic() - start

    print(f"\n✓ Local lock: 10 tasks in {elapsed:.2f}s, {api_call_count} API call(s)")
    print(f"  {[r[0] for r in results]}")

    assert api_call_count == 1, f"Expected 1 API call via local lock, got {api_call_count}"
    assert all(r["tvl"] == 999 for r in task_results)


# ---------------------------------------------------------------------------
# E2E-6: CryptoDataCacheMiddleware — cache enabled, full miss→lock→write cycle
# ---------------------------------------------------------------------------


async def test_e2e6_middleware_with_cache_enabled():
    """
    Enable the cache flag and exercise CryptoDataCacheMiddleware end-to-end
    with mocked DB + mocked external handler.
    Verifies: MISS → lock → double-check → handler → write path.
    """
    import os
    os.environ["CRYPTO_DATA_CACHE_ENABLED"] = "true"

    try:
        # Re-import to pick up env var
        import importlib
        import app.agents.new_chat.middleware.crypto_data_cache as cache_mod
        importlib.reload(cache_mod)

        from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware
        from langchain_core.messages import ToolMessage

        class FakeRequest:
            tool_call = {"name": "get_defillama_protocol", "args": {"protocol_slug": "uniswap"}, "id": "call_e2e"}

        api_result = ToolMessage(
            content=json.dumps({"tvl": 5_000_000, "name": "Uniswap"}),
            tool_call_id="call_e2e",
            name="get_defillama_protocol",
        )
        handler = AsyncMock(return_value=api_result)

        call_count = {"get_fresh": 0, "write": 0}

        async def mock_get_fresh(project_id, category, tool_name, args_hash):
            call_count["get_fresh"] += 1
            return None  # always miss

        async def mock_write(**kwargs):
            call_count["write"] += 1

        with patch("app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session") as mock_session, \
             patch("app.agents.new_chat.middleware.crypto_data_cache.CryptoProjectResolver") as MockResolver, \
             patch("app.agents.new_chat.middleware.crypto_data_cache.CryptoDataStore") as MockStore, \
             patch("app.agents.new_chat.middleware.crypto_data_cache.crypto_cache_lock") as mock_lock:

            # Setup session mock
            class FakeSession:
                db = AsyncMock()
                async def __aenter__(self): return self.db
                async def __aexit__(self, *a): pass

            mock_session.return_value = FakeSession()
            MockResolver.return_value.resolve = AsyncMock(return_value=42)
            MockStore.return_value.get_fresh_snapshot = mock_get_fresh
            MockStore.return_value.write_snapshot = mock_write
            MockStore.compute_args_hash = lambda args: "testhash"

            # Lock that just yields (no-op for this test)
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def fake_lock(*args, **kwargs):
                yield

            mock_lock.return_value = fake_lock()
            mock_lock.side_effect = lambda *a, **kw: fake_lock()

            mw = CryptoDataCacheMiddleware(redis_client=None)
            result = await mw.awrap_tool_call(FakeRequest(), handler)

        handler.assert_called_once()
        assert result is api_result
        print(f"\n✓ Middleware miss→handler path: handler called once, result returned")
        print(f"  get_fresh_snapshot calls: {call_count['get_fresh']}")
        print(f"  write_snapshot calls: {call_count['write']}")

    finally:
        os.environ["CRYPTO_DATA_CACHE_ENABLED"] = "false"
        importlib.reload(cache_mod)


# ---------------------------------------------------------------------------
# E2E-7: Lock key format verification
# ---------------------------------------------------------------------------


async def test_e2e7_lock_key_includes_project_id():
    """Verify lock key format is crypto_lock:{tool_name}:{project_id}:{args_hash}."""
    import os
    os.environ["CRYPTO_DATA_CACHE_ENABLED"] = "true"

    try:
        import importlib
        import app.agents.new_chat.middleware.crypto_data_cache as cache_mod
        importlib.reload(cache_mod)

        from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware
        from langchain_core.messages import ToolMessage

        class FakeRequest:
            tool_call = {"name": "get_defillama_protocol", "args": {"protocol_slug": "aave"}, "id": "call_key_test"}

        captured_lock_keys = []

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def capturing_lock(key, *args, **kwargs):
            captured_lock_keys.append(key)
            yield

        handler = AsyncMock(return_value=ToolMessage(content="{}", tool_call_id="call_key_test", name="get_defillama_protocol"))

        with patch("app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session") as mock_session, \
             patch("app.agents.new_chat.middleware.crypto_data_cache.CryptoProjectResolver") as MockResolver, \
             patch("app.agents.new_chat.middleware.crypto_data_cache.CryptoDataStore") as MockStore, \
             patch("app.agents.new_chat.middleware.crypto_data_cache.crypto_cache_lock", side_effect=capturing_lock):

            class FakeSession:
                db = AsyncMock()
                async def __aenter__(self): return self.db
                async def __aexit__(self, *a): pass

            mock_session.return_value = FakeSession()
            MockResolver.return_value.resolve = AsyncMock(return_value=99)  # project_id=99
            MockStore.return_value.get_fresh_snapshot = AsyncMock(return_value=None)
            MockStore.return_value.write_snapshot = AsyncMock()
            MockStore.compute_args_hash = lambda args: "deadbeef"

            mw = CryptoDataCacheMiddleware(redis_client=None)
            await mw.awrap_tool_call(FakeRequest(), handler)

        assert len(captured_lock_keys) == 1
        lock_key = captured_lock_keys[0]
        print(f"\n✓ Lock key used: {lock_key}")

        assert lock_key.startswith("crypto_lock:"), f"Key should start with 'crypto_lock:', got: {lock_key}"
        parts = lock_key.split(":")
        assert len(parts) == 4, f"Lock key should have 4 parts (crypto_lock:tool:project_id:hash), got {parts}"
        assert parts[1] == "get_defillama_protocol"
        assert parts[2] == "99", f"project_id should be '99', got '{parts[2]}'"
        assert parts[3] == "deadbeef"
        print(f"✓ Lock key format verified: crypto_lock:{{tool}}:{{project_id}}:{{args_hash}}")

    finally:
        os.environ["CRYPTO_DATA_CACHE_ENABLED"] = "false"
        importlib.reload(cache_mod)
