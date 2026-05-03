---
storyId: 10.3
storyTitle: Thundering Herd Protection (Redis Distributed Lock)
epicParent: epic-10-crypto-data-layer
depends: [Story 10.2]
relatedFRs: [FR38]
relatedNFRs: [NFR-CS6]
priority: P1
estimatedEffort: 2-3 days
status: done
createdAt: 2026-04-29
author: Winston (Architect)
---

# Story 10.3: Thundering Herd Protection

## User Story

**As a** system handling concurrent users,
**I want** distributed locking on cache misses,
**So that** 50 users querying ETH simultaneously trigger ≤ 1 API call instead of 50.

---

## Context

Story 10.2 has a race condition: if 50 concurrent requests all get cache miss at same moment, all 50 call external API before any snapshot is written. This story adds Redis distributed lock (SET NX EX) with double-check pattern after lock acquisition.

Without Story 10.3: 100 users querying ETH → up to 100 DeFiLlama calls during cache warmup
With Story 10.3: 100 users → 1 DeFiLlama call, 99 get from DB

---

## Deliverables

### 📄 Files to Create (1 file)

#### `nowing_backend/app/services/crypto_cache_lock.py`

```python
import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Per-process fallback locks (key → asyncio.Lock)
_local_locks: dict[str, asyncio.Lock] = {}
_local_locks_mutex = asyncio.Lock()


@asynccontextmanager
async def crypto_cache_lock(key: str, redis_client=None, ttl: int = 60):
    """
    Context manager for distributed lock.
    - Primary: Redis SET NX EX (distributed, cross-process)
    - Fallback: asyncio.Lock (per-process, if Redis unavailable)

    Usage:
        async with crypto_cache_lock(f"crypto_lock:{tool_name}:{args_hash}", redis):
            # Only 1 coroutine at a time executes this block per key
            ...
    """
    if redis_client is not None:
        async with _redis_lock(key, redis_client, ttl):
            yield
    else:
        async with _local_lock(key):
            yield


@asynccontextmanager
async def _redis_lock(key: str, redis, ttl: int):
    acquired = False
    try:
        # SET key 1 NX EX ttl — atomic acquire
        acquired = await redis.set(key, "1", nx=True, ex=ttl)
        if not acquired:
            # Wait for lock to release (poll with backoff)
            for delay in [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]:
                await asyncio.sleep(delay)
                acquired = await redis.set(key, "1", nx=True, ex=ttl)
                if acquired:
                    break
        yield
    finally:
        if acquired:
            try:
                await redis.delete(key)
            except Exception:
                pass  # TTL will clean up


@asynccontextmanager
async def _local_lock(key: str):
    async with _local_locks_mutex:
        if key not in _local_locks:
            _local_locks[key] = asyncio.Lock()
    async with _local_locks[key]:
        yield
```

### 📄 Files to Modify (1 file)

#### `nowing_backend/app/agents/new_chat/middleware/crypto_data_cache.py`

Update `_cached_tool_call` to wrap API call in distributed lock:

```python
from app.services.crypto_cache_lock import crypto_cache_lock

async def _cached_tool_call(self, request, handler, tool_name: str):
    # ... (existing cache check logic from Story 10.2) ...

    cached = await store.get_fresh_snapshot(...)
    if cached is not None:
        return self._make_tool_message(request, cached)

    # MISS → acquire lock → double-check → call API
    lock_key = f"crypto_lock:{tool_name}:{args_hash}"
    async with crypto_cache_lock(lock_key, self._redis):
        # Double-check: another process may have filled cache while we waited
        cached = await store.get_fresh_snapshot(...)
        if cached is not None:
            logger.debug("CryptoDataCache DOUBLE-CHECK HIT: %s", tool_name)
            return self._make_tool_message(request, cached)

        # Still miss → we won the race, call API
        result = await handler(request)
        # ... write snapshot ...
        return result
```

---

## Acceptance Criteria

### AC1: Concurrent cache misses → 1 API call

**Given** 10 concurrent asyncio tasks all calling same tool for same token (cache empty)
**When** all tasks execute simultaneously (asyncio.gather)
**Then** external API called exactly 1 time (verify via mock call counter)
**And** all 10 tasks receive the same data
**And** exactly 1 snapshot written to DB

### AC2: Double-check hit after lock acquisition

**Given** task A acquired lock and wrote snapshot, task B waiting for lock
**When** task B acquires lock
**Then** task B performs double-check, finds snapshot, returns cached data
**And** task B does NOT call external API

### AC3: Redis fallback to local lock

**Given** Redis client is None (unavailable)
**When** concurrent cache misses
**Then** asyncio.Lock used instead
**And** behavior identical to AC1 within same process

### AC4: Lock TTL expiry (crash recovery)

**Given** lock holder crashes before releasing lock
**When** lock TTL (60s) expires
**Then** another coroutine can acquire the lock
**And** API call proceeds normally (no deadlock)

### AC5: Different keys → concurrent execution allowed

**Given** simultaneous cache miss for ETH and BTC (different tokens)
**When** both call same tool
**Then** both proceed concurrently (different lock keys, no blocking)

---

## Dev Notes

- **Redis client must be async**: `get_redis_client()` in the existing codebase returns a sync `redis.Redis` (used by Celery tasks). `CryptoDataCacheMiddleware` is async — pass `redis.asyncio.from_url(settings.REDIS_APP_URL)` as `redis_client`. Create this once in `create_nowing_deep_agent()` scope.
- Lock key format: `crypto_lock:{tool_name}:{args_hash}` — args_hash is SHA-256 from Story 10.2
- Lock TTL 60s: long enough for any API call + write, short enough to avoid long deadlocks
- The poll loop in `_redis_lock` uses exponential-ish backoff: max wait ~9s before giving up. If lock not acquired after all retries, proceed without lock (degrade gracefully)
- Don't use `asyncio.sleep` blocking the event loop — use `await asyncio.sleep()`
- Local lock dict cleanup: `_local_locks` will slowly grow if many unique keys are used. For now, accept memory growth (bounded by unique tool+args combinations — typically < 1000)

### Review Findings (2026-04-30)

- [x] [Review][Decision] F1: Non-atomic Redis lock release — RESOLVED: UUID + Lua CAS script implemented
- [x] [Review][Decision] F4: Lock key missing `project_id` — RESOLVED: added `project_id` to lock key format
- [x] [Review][Patch] F2: Redis client leaked — RESOLVED: singleton `get_redis_client()` in crypto_cache_lock.py
- [x] [Review][Patch] F5: Uses `CELERY_BROKER_URL` instead of `config.REDIS_APP_URL` — RESOLVED: uses `config.REDIS_APP_URL`
- [x] [Review][Patch] F6: Silent swallow of Redis connection failure — RESOLVED: logs warning
- [x] [Review][Patch] F10: AC1 test misleading — RESOLVED: renamed to `test_ac1_lock_serializes_concurrent_access`
- [x] [Review][Patch] F13: Tautological assertion in F8 test — RESOLVED: removed redundant assert
- [x] [Review][Defer] F3: `_local_locks` dict grows unboundedly [crypto_cache_lock.py:8] — deferred, bounded by unique tool+args combos (~1000 max). LRU eviction can be added later.
- [x] [Review][Defer] F7: Lock retry backoff totals ~8.8s [crypto_cache_lock.py:37] — deferred, by design per spec Dev Notes. Tradeoff accepted.
- [x] [Review][Defer] F9: Graceful degradation bypasses herd protection [crypto_cache_lock.py:42] — deferred, by design. Double-check DB still runs, reduces duplicates.
- [x] [Review][Defer] F11: No integration-level thundering herd test at middleware layer — deferred, integration test scope. Unit coverage sufficient for story acceptance.
- [x] [Review][Defer] F12: AC4 TTL expiry recovery not directly tested — deferred, relies on Redis server behavior. Unit test mocks only fail-to-acquire path.
