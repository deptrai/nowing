---
storyId: 10.4
storyTitle: Background Data Refresh (Celery)
epicParent: epic-10-crypto-data-layer
depends: [Story 10.1]
relatedFRs: [FR39]
relatedNFRs: [NFR-CS5]
priority: P2
estimatedEffort: 2-3 days
status: done
createdAt: 2026-04-29
author: Winston (Architect)
---

# Story 10.4: Background Data Refresh

## User Story

**As a** system operator,
**I want** Celery beat tasks to pre-warm popular token data before TTL expiry,
**So that** active users rarely experience cache misses for frequently queried tokens.

---

## Context

Story 10.2-10.3 handle reactive caching (cache on demand). Story 10.4 adds proactive pre-warming: find tokens queried recently, pre-fetch before they expire.

Without Story 10.4: cache cold every TTL window for popular tokens
With Story 10.4: top-10 tokens stay warm continuously → cache hit rate targets (NFR-CS5: ≥70%) achievable

Second task: cleanup to prevent unbounded DB growth.

---

## Deliverables

### 📄 Files to Create (1 file)

#### `nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py`

```python
from celery import shared_task
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(name="crypto.refresh_popular_data", bind=True, max_retries=0)
def refresh_popular_crypto_data(self):
    """
    Runs every 30 minutes via Celery beat.
    Finds tokens queried in last 24h with snapshots expiring within 5 minutes.
    Pre-fetches those categories to avoid cold cache.
    """
    import asyncio
    asyncio.run(_async_refresh_popular())


async def _async_refresh_popular():
    now = datetime.now(timezone.utc)
    expiry_window = now + timedelta(minutes=5)
    since = now - timedelta(hours=24)

    from app.db import shielded_async_session
    async with shielded_async_session() as db:
        # Find snapshots expiring soon for recently-queried tokens
        expiring = await db.execute(
            select(
                CryptoDataSnapshot.project_id,
                CryptoDataSnapshot.data_category,
                CryptoDataSnapshot.tool_name,
                CryptoDataSnapshot.tool_args,
            )
            .where(
                CryptoDataSnapshot.fetched_at >= since,
                CryptoDataSnapshot.expires_at <= expiry_window,
                CryptoDataSnapshot.expires_at > now,
                CryptoDataSnapshot.is_error == False,
            )
            .distinct()
        )
        rows = expiring.fetchall()

    logger.info("CryptoRefresh: %d snapshots expiring within 5 min", len(rows))

    for row in rows:
        try:
            await _prefetch_category(row.project_id, row.data_category, row.tool_name, row.tool_args)
        except Exception as exc:
            logger.warning("CryptoRefresh prefetch failed for %s/%s: %s",
                           row.tool_name, row.data_category, exc)
            # continue with next — don't crash entire task


async def _prefetch_category(project_id, category, tool_name, tool_args):
    """Calls the actual tool function directly (not via agent) to refresh cache."""
    from app.services.crypto_data_store import CryptoDataStore
    from app.agents.new_chat.tools.crypto_data_categories import TOOL_CATEGORY_MAP, TTL_SECONDS
    from app.agents.new_chat.tools.registry import BUILTIN_TOOLS
    from app.db import shielded_async_session

    # Build tool function lookup from registry — get_tool_function() does not exist;
    # use factory pattern instead. Only include tools with no required context (requires=[]).
    tool_fn_map = {td.name: td.factory() for td in BUILTIN_TOOLS if not td.requires}
    tool_fn = tool_fn_map.get(tool_name)
    if tool_fn is None:
        logger.debug("CryptoRefresh: tool %s not in registry or requires context, skipping", tool_name)
        return

    result = await tool_fn(**(tool_args or {}))
    if not isinstance(result, dict) or result.get("error"):
        logger.debug("CryptoRefresh: tool %s returned error, storing with short TTL", tool_name)

    async with shielded_async_session() as db:
        store = CryptoDataStore(db)
        _, api_source = TOOL_CATEGORY_MAP[tool_name]
        is_error = bool(isinstance(result, dict) and result.get("error"))
        await store.write_snapshot(
            project_id=project_id,
            category=category,
            tool_name=tool_name,
            tool_args=tool_args,
            data=result,
            ttl_seconds=300 if is_error else TTL_SECONDS[category],
            api_source=api_source,
            is_error=is_error,
        )


@shared_task(name="crypto.cleanup_expired_snapshots", bind=True, max_retries=0)
def cleanup_expired_crypto_snapshots(self):
    """
    Runs daily at 3 AM UTC via Celery beat.
    - Deletes snapshots older than 30 days
    - Deletes error snapshots older than 24h
    - Prunes per-project/category to max 1000 snapshots
    """
    import asyncio
    asyncio.run(_async_cleanup())


async def _async_cleanup():
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    cutoff_24h = now - timedelta(hours=24)

    from app.db import shielded_async_session
    async with shielded_async_session() as db:
        # Delete old snapshots
        result = await db.execute(
            delete(CryptoDataSnapshot).where(CryptoDataSnapshot.created_at < cutoff_30d)
        )
        logger.info("CryptoCleanup: deleted %d snapshots > 30 days", result.rowcount)

        # Delete old error snapshots
        result = await db.execute(
            delete(CryptoDataSnapshot).where(
                CryptoDataSnapshot.is_error == True,
                CryptoDataSnapshot.created_at < cutoff_24h,
            )
        )
        logger.info("CryptoCleanup: deleted %d error snapshots > 24h", result.rowcount)

        await db.commit()

    # Prune per-project/category to max 1000 (keep newest)
    await _prune_per_category()
```

### 📄 Files to Modify (1 file)

#### `nowing_backend/app/celery_app.py`

Add to beat_schedule:
```python
app.conf.beat_schedule.update({
    "crypto-refresh-popular-data": {
        "task": "crypto.refresh_popular_data",
        "schedule": crontab(minute="*/30"),  # every 30 minutes
    },
    "crypto-cleanup-expired-snapshots": {
        "task": "crypto.cleanup_expired_snapshots",
        "schedule": crontab(hour=3, minute=0),  # daily 3 AM UTC
    },
})
```

---

## Acceptance Criteria

### AC1: Refresh task finds expiring snapshots

**Given** DB has 5 snapshots for ETH categories expiring within 5 minutes
**When** `refresh_popular_crypto_data` runs
**Then** task calls external APIs for those 5 categories
**And** new snapshots written with updated `expires_at`

### AC2: Rate limit handling — skip, don't crash

**Given** DeFiLlama API returns 429 for one category during refresh
**When** task runs
**Then** logs warning for that category
**And** continues refreshing other categories
**And** task completes successfully (no crash, no retry)

### AC3: Cleanup — 30-day retention

**Given** snapshots with `created_at < 30 days ago`
**When** `cleanup_expired_crypto_snapshots` runs
**Then** those rows deleted
**And** snapshots newer than 30 days remain

### AC4: Cleanup — error snapshot 24h retention

**Given** error snapshots (`is_error=True`) older than 24h
**When** cleanup task runs
**Then** deleted
**And** recent error snapshots (< 24h) remain

### AC5: Beat schedule registered

**Given** app starts with Celery beat
**When** `celery inspect scheduled`
**Then** both tasks appear in beat schedule with correct intervals

---

## Dev Notes

- **`get_tool_function()` does not exist** in `registry.py`. Use `{td.name: td.factory() for td in BUILTIN_TOOLS if not td.requires}` to build a lookup dict. Only tools with no required context (`requires=[]` or `requires` not set) can be called standalone — all current crypto tools qualify.
- Celery task uses `asyncio.run()` because Celery workers are sync by default. If app uses `celery[gevent]` or async Celery, adapt accordingly
- **Session management**: Use `shielded_async_session()` (cancellation-safe) for all DB ops in both refresh and cleanup tasks. Do NOT import `get_async_session` — that is a FastAPI dependency generator designed for request scope.
- `_prune_per_category` — can use DELETE with subquery: `DELETE WHERE id NOT IN (SELECT id FROM snapshots WHERE project_id=X AND data_category=Y ORDER BY fetched_at DESC LIMIT 1000)`
- Don't run cleanup in same transaction as regular writes — separate `async with shielded_async_session()`
- Refresh task should respect `CRYPTO_DATA_CACHE_ENABLED` flag: if `false`, skip (no point refreshing if cache is disabled)

---

## Dev Agent Record

### Implementation Notes (2026-04-30)

**Files Created:**
- `nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py` — 2 Celery tasks + async helpers

**Files Modified:**
- `nowing_backend/app/celery_app.py` — added `crypto_refresh_tasks` to `include[]` + 2 beat schedule entries

**Tests Created:**
- `nowing_backend/tests/unit/tasks/test_crypto_refresh_tasks.py` — 6 unit tests (AC1–AC5 + cache-disabled guard)

### Completion Notes

- AC1 ✅ `_async_refresh_popular`: queries snapshots expiring within 5 min last 24h, calls `_prefetch_category` per row
- AC2 ✅ Per-row exception caught, logs warning, continues to next row — task never crashes
- AC3 ✅ `_async_cleanup` issues `DELETE WHERE created_at < 30 days ago`
- AC4 ✅ `_async_cleanup` issues separate `DELETE WHERE is_error=True AND created_at < 24h`
- AC5 ✅ Both tasks registered in `celery_app.conf.beat_schedule` (verified by unit test)
- Dev Note deviation: used `get_celery_session_maker()` instead of `shielded_async_session()` per existing Celery task pattern in codebase (stale_notification_cleanup_task.py). `shielded_async_session` is FastAPI request-scope only.
- Dev Note deviation: `td.factory({})` to instantiate tools (pass empty deps dict) instead of `td.factory()` — matches `ToolDefinition.factory: Callable[[dict], BaseTool]` signature.

### File List

| File | Action |
|------|--------|
| `nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py` | CREATE |
| `nowing_backend/app/celery_app.py` | MODIFY |
| `nowing_backend/tests/unit/tasks/test_crypto_refresh_tasks.py` | CREATE |

### Change Log

- 2026-04-30: Story 10.4 implemented — 2 Celery tasks (refresh + cleanup), beat schedule registered, 6 unit tests pass
- 2026-05-01: Code review complete — 1 decision-needed, 4 patches, 3 deferred, 9 dismissed

### Review Findings

- [x] [Review][Decision] **Cleanup DELETEs share single session** — resolved: split to 2 separate sessions (spec-compliant). [`crypto_refresh_tasks.py:150-172`]

- [x] [Review][Patch] **`_prefetch_category` rebuilds tool_fn_map on every row** — move `tool_fn_map` construction to `_async_refresh_popular` and pass as arg [`crypto_refresh_tasks.py:88`]
- [x] [Review][Patch] **`test_refresh_skips_when_cache_disabled` never invokes the task** — test asserts `mock_loop.assert_not_called()` without calling `refresh_popular_crypto_data()`. Test proves nothing. [`test_crypto_refresh_tasks.py:238-253`]
- [x] [Review][Patch] **AC5 test doesn't validate schedule intervals** — should assert `crontab(minute="*/30")` and `crontab(hour=3, minute=0)` [`test_crypto_refresh_tasks.py:214-230`]
- [x] [Review][Patch] **DISTINCT over JSONB `tool_args` may cause duplicate API calls** — use `args_hash` column instead for dedup in refresh query [`crypto_refresh_tasks.py:49-63`]

- [x] [Review][Defer] **`asyncio.set_event_loop(None)` / `shutdown_asyncgens()` not called** — pre-existing pattern from `stale_notification_cleanup_task.py`. Not a regression. [`crypto_refresh_tasks.py:29-33,126-130`]
- [x] [Review][Defer] **No rate limiting on prefetch calls** — valid but out of scope for AC2 (which only requires "skip, don't crash"). [`crypto_refresh_tasks.py:68-79`]
- [x] [Review][Defer] **`NOT IN (SELECT ... LIMIT)` prune SQL potentially slow** — acceptable at current scale (<1000 rows/pair). Revisit when data grows. [`crypto_refresh_tasks.py:173-203`]
