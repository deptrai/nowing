---
storyId: 10.2
storyTitle: CryptoDataCacheMiddleware
epicParent: epic-10-crypto-data-layer
depends: [Story 10.1]
blocks: [Story 10.3]
relatedFRs: [FR37]
relatedNFRs: [NFR-CS5, NFR-CS6]
priority: P0
estimatedEffort: 3-4 days
status: done
createdAt: 2026-04-29
author: Winston (Architect)
---

# Story 10.2: CryptoDataCacheMiddleware

## User Story

**As a** sub-agent making crypto tool calls,
**I want** tool results transparently served from DB cache when fresh,
**So that** external API calls are skipped for data already fetched within TTL, with zero changes to existing tool code or sub-agent behavior.

---

## Context

This story implements the core cache interception. Pattern follows `SourceAttributionMiddleware` in `chat_deepagent.py` — same `awrap_tool_call` hook. Placement: AFTER `SourceAttributionMiddleware` (so narration events always fire, whether data is cached or fresh).

Feature flag `CRYPTO_DATA_CACHE_ENABLED=false` → middleware is complete pass-through (zero overhead, safe default).

---

## Deliverables

### 📄 Files to Create (1 file)

#### `nowing_backend/app/agents/new_chat/middleware/crypto_data_cache.py`

```python
import hashlib, json, logging
from langchain_core.messages import AIMessage, ToolMessage
from deepagents import BaseMiddleware, Request, Handler

from app.agents.new_chat.tools.crypto_data_categories import TOOL_CATEGORY_MAP, TTL_SECONDS
from app.services.crypto_project_resolver import CryptoProjectResolver
from app.services.crypto_data_store import CryptoDataStore
from app.core.config import settings
from app.db import shielded_async_session  # cancellation-safe session for agent context

logger = logging.getLogger(__name__)

class CryptoDataCacheMiddleware(BaseMiddleware):
    """
    Intercepts crypto tool calls to serve cached results from DB.
    Transparent to sub-agents: same response format whether cached or fresh.
    Placed AFTER SourceAttributionMiddleware so narration events always fire.

    Uses shielded_async_session() for each DB op — short-lived sessions owned by
    this middleware, NOT the HTTP-request-scoped session from create_nowing_deep_agent().
    """

    def __init__(self, redis_client=None):
        # No db_session param — open short-lived sessions per cache op via shielded_async_session()
        self._redis = redis_client

    async def awrap_tool_call(self, request: Request, handler: Handler) -> AIMessage | ToolMessage:
        if not settings.CRYPTO_DATA_CACHE_ENABLED:
            return await handler(request)

        tool_name = self._extract_tool_name(request)
        if tool_name not in TOOL_CATEGORY_MAP:
            return await handler(request)

        try:
            return await self._cached_tool_call(request, handler, tool_name)
        except Exception as exc:
            logger.warning("CryptoDataCache error, falling back to direct API: %s", exc)
            return await handler(request)

    async def _cached_tool_call(self, request, handler, tool_name: str):
        category, api_source = TOOL_CATEGORY_MAP[tool_name]
        ttl = TTL_SECONDS[category]
        tool_args = self._extract_tool_args(request)
        args_hash = self._hash_args(tool_args)

        # Use shielded_async_session: cancellation-safe, short-lived, independent of HTTP session
        async with shielded_async_session() as db:
            resolver = CryptoProjectResolver(db)
            store = CryptoDataStore(db)

            project_id = await resolver.resolve(tool_name, tool_args)
            if project_id is None:
                return await handler(request)

            # Check cache
            cached = await store.get_fresh_snapshot(project_id, category, tool_name, args_hash)
            if cached is not None:
                logger.debug("CryptoDataCache HIT: %s/%s project_id=%s", tool_name, category, project_id)
                return self._make_tool_message(request, cached)

        # Cache miss → call API (outside DB session to avoid holding connection during API call)
        logger.debug("CryptoDataCache MISS: %s/%s", tool_name, category)
        result = await handler(request)
        data = self._extract_result_data(result)

        # Write snapshot in separate session (fire-and-forget friendly)
        try:
            async with shielded_async_session() as db:
                resolver = CryptoProjectResolver(db)
                store = CryptoDataStore(db)
                project_id = await resolver.resolve(tool_name, tool_args)
                if project_id is not None:
                    is_error = isinstance(data, dict) and bool(data.get("error"))
                    await store.write_snapshot(
                        project_id=project_id,
                        category=category,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        data=data,
                        ttl_seconds=300 if is_error else ttl,  # short TTL for errors
                        api_source=api_source,
                        is_error=is_error,
                    )
        except Exception as write_exc:
            logger.warning("CryptoDataCache write failed (non-fatal): %s", write_exc)

        return result

    def _extract_tool_name(self, request) -> str: ...
    def _extract_tool_args(self, request) -> dict: ...
    def _extract_result_data(self, result) -> dict: ...
    def _make_tool_message(self, request, data: dict): ...
    def _hash_args(self, args: dict) -> str:
        return hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()
```

### 📄 Files to Modify (2 files)

#### `nowing_backend/app/agents/new_chat/chat_deepagent.py`

Add to `_build_gp_middleware()` (line ~2268) ONLY — **do NOT add to `deepagent_middleware`** (main agent stack, lines ~2403-2445).

Rationale: sub-agents make direct crypto API calls. The main orchestrator uses `task()` to spawn sub-agents, so adding cache there has no effect and adds overhead.

```python
from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware

# Inside _build_gp_middleware() — AFTER SourceAttributionMiddleware:
def _build_gp_middleware(agent_name: str = "subagent") -> list[Any]:
    return [
        ProviderRateLimitMiddleware(),
        SourceAttributionMiddleware(agent_name=agent_name),   # existing
        CryptoDataCacheMiddleware(redis_client=_redis_client),  # NEW — no db param
        TodoListMiddleware(),
        # ... rest unchanged
    ]
```

`_redis_client` — create once in `create_nowing_deep_agent()` scope using `redis.asyncio`:
```python
import redis.asyncio as aioredis
from app.core.config import settings

_redis_client = aioredis.from_url(settings.REDIS_APP_URL, decode_responses=True)
```

Note: existing `get_redis_client()` returns a **sync** `redis.Redis` — do NOT reuse it here.

#### `nowing_backend/app/agents/new_chat/middleware/__init__.py`

Add export:
```python
from .crypto_data_cache import CryptoDataCacheMiddleware
```

---

## Acceptance Criteria

### AC1: Cache hit — no API call

**Given** `CRYPTO_DATA_CACHE_ENABLED=true` and fresh snapshot in DB for `get_defillama_protocol("uniswap")`
**When** defillama_analyst sub-agent calls `get_defillama_protocol("uniswap")`
**Then** DeFiLlama API NOT called (verify via mock/spy)
**And** returned data == cached data
**And** `SourceAttributionMiddleware` events fire (narration, source domain) — identical to non-cached path

### AC2: Cache miss → API call → write

**Given** no snapshot in DB
**When** defillama_analyst calls `get_defillama_protocol("uniswap")`
**Then** DeFiLlama API called once
**And** result returned to agent
**And** `crypto_data_snapshots` row created with correct `expires_at = NOW() + 3600s`

### AC3: Cache disabled → pass-through

**Given** `CRYPTO_DATA_CACHE_ENABLED=false`
**When** any crypto tool called
**Then** middleware calls handler directly
**And** no DB queries issued
**And** response identical to pre-Epic10 behavior

### AC4: Graceful degradation — DB error

**Given** DB connection fails mid-lookup
**When** crypto tool called
**Then** middleware catches exception, calls handler directly
**And** tool result returned normally to agent
**And** warning logged (not error — non-fatal)

### AC5: Non-crypto tools — pass-through

**Given** tool_name not in `TOOL_CATEGORY_MAP` (e.g., `generate_report`, `chainlens_deep_research`)
**When** tool called
**Then** middleware is complete pass-through (no DB queries, no logging)

### AC6: Error results not cached with normal TTL

**Given** API call returns error dict `{"error": "rate_limited"}`
**When** result written to DB
**Then** snapshot stored with `is_error=True`, `ttl_seconds=300` (5 min short TTL)
**And** `get_fresh_snapshot()` will NOT return this snapshot (is_error=true filter)

---

## Dev Notes

- Study `SourceAttributionMiddleware.awrap_tool_call()` in `chat_deepagent.py` lines ~806-971 for exact middleware API pattern
- The `_make_tool_message()` helper must construct the same ToolMessage format as the original handler — check how `SourceAttributionMiddleware` handles the result before wrapping
- **Session management**: Do NOT pass `db_session` from `create_nowing_deep_agent()` into this middleware — that session is HTTP-request-scoped and may expire during long agent runs. Use `shielded_async_session()` (db.py:2515) for each DB operation — it's cancellation-safe and creates independent short-lived connections.
- **Redis**: Existing `get_redis_client()` returns sync `redis.Redis` (used by Celery tasks). Middleware is async — use `redis.asyncio.from_url(settings.REDIS_APP_URL)` instead. Create once per agent invocation in `create_nowing_deep_agent()` scope.
- **Middleware placement**: Add to `_build_gp_middleware()` (line ~2268) ONLY — this is called once per sub-agent spec. Do NOT add to `deepagent_middleware` (lines ~2403-2445) — main agent spawns sub-agents via `task()`, not direct tool calls.
- **Error handling**: Write errors short TTL (300s) with `is_error=True`; `get_fresh_snapshot()` filters them out. This prevents stale errors from blocking retries.
- Thundering herd (Story 10.3) not in this story — implement basic cache check first, distributed lock comes next

---

### Review Findings

- [x] [Review][Decision] F5: `get_fear_greed_index` treated as per-project but is global market indicator — resolved: synthetic `global:fear_greed` project_id
- [x] [Review][Patch] F1: CRITICAL — `args_hash` unused in `get_fresh_snapshot()` WHERE clause; no `args_hash` column in `CryptoDataSnapshot` model — fixed: added column + index + WHERE filter
- [x] [Review][Patch] F2: Read session never commits → `CryptoProjectResolver.resolve()` INSERT rolled back — fixed: added `await db.commit()` in read session
- [x] [Review][Patch] F3: `updated_at` column in migration 138 but missing from `CryptoProject` ORM model — fixed: added `updated_at` with `onupdate`
- [x] [Review][Patch] F4: `tool_call_id` can be None → `ToolMessage(tool_call_id=None)` may fail — fixed: `or ""` fallback
- [x] [Review][Patch] F6: Double `resolver.resolve()` on cache miss — fixed: pass `project_id` from read to write path
- [x] [Review][Patch] F8: Tests don't verify `args_hash` discrimination — fixed: added `test_f8_different_args_yield_cache_miss`
- [x] [Review][Defer] F7: `dune_onchain` category in spec but intentionally excluded from implementation (comment explains) — deferred, spec/impl drift documentation
