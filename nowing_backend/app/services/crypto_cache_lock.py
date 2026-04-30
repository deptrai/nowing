import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Per-process fallback locks (key → asyncio.Lock)
_local_locks: dict[str, asyncio.Lock] = {}
_local_locks_mutex = asyncio.Lock()

# Lua script: delete key only if current value matches our token (owner check)
_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Module-level singleton Redis client — shared across all agent invocations.
_redis_singleton = None
_redis_init_done = False


def get_redis_client():
    """Return the shared async Redis client, or None if unavailable."""
    global _redis_singleton, _redis_init_done
    if _redis_init_done:
        return _redis_singleton
    _redis_init_done = True
    try:
        import redis.asyncio as aioredis
        from app.config import config
        _redis_singleton = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    except Exception as exc:
        logger.warning("crypto_cache_lock: Redis unavailable, using local locks: %s", exc)
        _redis_singleton = None
    return _redis_singleton


@asynccontextmanager
async def crypto_cache_lock(key: str, redis_client=None, ttl: int = 60):
    """
    Distributed lock for cache-miss serialization (thundering herd protection).

    Primary: Redis SET NX EX (cross-process, distributed).
    Fallback: asyncio.Lock (per-process, when Redis is unavailable).

    After acquiring the lock, callers should double-check the cache before
    making an external API call — another holder may have filled it.
    """
    if redis_client is not None:
        async with _redis_lock(key, redis_client, ttl):
            yield
    else:
        async with _local_lock(key):
            yield


@asynccontextmanager
async def _redis_lock(key: str, redis, ttl: int):
    token = str(uuid.uuid4())
    acquired = False
    try:
        acquired = await redis.set(key, token, nx=True, ex=ttl)
        if not acquired:
            for delay in [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]:
                await asyncio.sleep(delay)
                acquired = await redis.set(key, token, nx=True, ex=ttl)
                if acquired:
                    break
            if not acquired:
                logger.warning("crypto_cache_lock: could not acquire Redis lock for %s, proceeding unlocked", key)
        yield
    finally:
        if acquired:
            try:
                await redis.eval(_RELEASE_SCRIPT, 1, key, token)
            except Exception:
                pass  # TTL will clean up


@asynccontextmanager
async def _local_lock(key: str):
    async with _local_locks_mutex:
        if key not in _local_locks:
            _local_locks[key] = asyncio.Lock()
    async with _local_locks[key]:
        yield
