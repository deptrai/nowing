"""Celery tasks for proactive crypto data cache refresh and cleanup.

Three tasks:
  - refresh_popular_crypto_data: every 30 min — pre-warm tokens expiring soon
  - cleanup_expired_crypto_snapshots: daily 3 AM UTC — prune old rows
  - cleanup_orphaned_crypto_snapshots: weekly Sunday 4 AM UTC — purge dead-workspace rows
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text

from app.celery_app import celery_app
from app.db import CryptoDataSnapshot
from app.tasks.celery_tasks import get_celery_session_maker

logger = logging.getLogger(__name__)

# Dedicated logger for structured-JSON metric lines so the message body stays
# parseable even when the root Celery formatter prepends timestamps to other
# loggers. Operators can configure `crypto.metrics` with a JSON-only formatter
# (no prefix) when shipping to CloudWatch/Datadog. Falls back to the standard
# logger if no special handler is configured.
metric_logger = logging.getLogger("crypto.metrics")


# ---------------------------------------------------------------------------
# Task 1: Proactive refresh
# ---------------------------------------------------------------------------


@celery_app.task(name="crypto.refresh_popular_data", bind=True, max_retries=0)
def refresh_popular_crypto_data(self):
    """Every 30 min: pre-warm snapshots expiring within 5 min for tokens active last 24h."""
    from app.agents.new_chat.middleware.crypto_data_cache import _CACHE_ENABLED

    if not _CACHE_ENABLED:
        logger.debug("CryptoRefresh: cache disabled, skipping")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_refresh_popular())
    finally:
        loop.close()


async def _async_refresh_popular():
    now = datetime.now(UTC)
    expiry_window = now + timedelta(minutes=5)
    since = now - timedelta(hours=24)

    async with get_celery_session_maker()() as db:
        result = await db.execute(
            select(
                CryptoDataSnapshot.project_id,
                CryptoDataSnapshot.data_category,
                CryptoDataSnapshot.tool_name,
                CryptoDataSnapshot.tool_args,
                CryptoDataSnapshot.args_hash,
            )
            .where(
                CryptoDataSnapshot.fetched_at >= since,
                CryptoDataSnapshot.expires_at <= expiry_window,
                CryptoDataSnapshot.expires_at > now,
                CryptoDataSnapshot.is_error.is_(False),
            )
            .distinct(
                CryptoDataSnapshot.project_id,
                CryptoDataSnapshot.data_category,
                CryptoDataSnapshot.tool_name,
                CryptoDataSnapshot.args_hash,
            )
        )
        rows = result.fetchall()

    logger.info("CryptoRefresh: %d snapshots expiring within 5 min", len(rows))

    if not rows:
        return

    from app.agents.new_chat.tools.registry import BUILTIN_TOOLS

    tool_fn_map = {td.name: td.factory({}) for td in BUILTIN_TOOLS if not td.requires}

    for row in rows:
        try:
            await _prefetch_category(
                row.project_id, row.data_category, row.tool_name, row.tool_args, tool_fn_map
            )
        except Exception as exc:
            logger.warning(
                "CryptoRefresh prefetch failed for %s/%s: %s",
                row.tool_name,
                row.data_category,
                exc,
            )


async def _prefetch_category(project_id, category, tool_name, tool_args, tool_fn_map):
    """Call the tool function directly (no agent context) to refresh a single snapshot.

    **Bi-modal cache (ADR-013, Story 11.7 T4):** This refresh path produces
    GLOBAL cache rows (`search_space_id IS NULL`) — the proactive refresh
    task is intentionally workspace-agnostic. Per-workspace cache rows are
    only written by user-triggered tool calls inside a workspace-scoped chat
    (via the agent middleware path), not by this task. The weekly
    `cleanup_orphaned_crypto_snapshots` task purges per-workspace orphans
    only and leaves these global rows for TTL-based eviction.
    """
    from app.agents.new_chat.tools.crypto_data_categories import TOOL_CATEGORY_MAP, TTL_SECONDS
    from app.services.crypto_data_store import CryptoDataStore

    tool_fn = tool_fn_map.get(tool_name)
    if tool_fn is None:
        logger.debug(
            "CryptoRefresh: tool %s not in registry or requires context, skipping", tool_name
        )
        return

    if tool_name not in TOOL_CATEGORY_MAP:
        logger.debug("CryptoRefresh: tool %s not in TOOL_CATEGORY_MAP, skipping", tool_name)
        return

    result = await tool_fn.ainvoke(tool_args or {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {"raw": result}

    is_error = bool(isinstance(result, dict) and result.get("error"))
    _, api_source = TOOL_CATEGORY_MAP[tool_name]
    ttl = 300 if is_error else TTL_SECONDS[category]

    async with get_celery_session_maker()() as db:
        store = CryptoDataStore(db)
        await store.write_snapshot(
            project_id=project_id,
            category=category,
            tool_name=tool_name,
            tool_args=tool_args,
            data=result if isinstance(result, dict) else {"value": result},
            ttl_seconds=ttl,
            api_source=api_source,
            is_error=is_error,
        )
        await db.commit()

    logger.debug("CryptoRefresh: refreshed %s/%s for project %s", tool_name, category, project_id)


# ---------------------------------------------------------------------------
# Task 2: Cleanup
# ---------------------------------------------------------------------------


@celery_app.task(name="crypto.cleanup_expired_snapshots", bind=True, max_retries=0)
def cleanup_expired_crypto_snapshots(self):
    """Daily 3 AM UTC: delete stale rows and prune per-project/category to max 1000."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_cleanup())
    finally:
        loop.close()


async def _async_cleanup():
    now = datetime.now(UTC)
    cutoff_30d = now - timedelta(days=30)
    cutoff_24h = now - timedelta(hours=24)

    async with get_celery_session_maker()() as db:
        result = await db.execute(
            delete(CryptoDataSnapshot).where(
                CryptoDataSnapshot.created_at < cutoff_30d
            )
        )
        logger.info("CryptoCleanup: deleted %d snapshots older than 30 days", result.rowcount)
        await db.commit()

    async with get_celery_session_maker()() as db:
        result = await db.execute(
            delete(CryptoDataSnapshot).where(
                CryptoDataSnapshot.is_error.is_(True),
                CryptoDataSnapshot.created_at < cutoff_24h,
            )
        )
        logger.info(
            "CryptoCleanup: deleted %d error snapshots older than 24h", result.rowcount
        )
        await db.commit()

    await _prune_per_category()


async def _prune_per_category(max_rows: int = 1000):
    """Keep only the newest `max_rows` snapshots per (project_id, data_category) pair."""
    async with get_celery_session_maker()() as db:
        # Find all (project_id, data_category) pairs that exceed the limit
        overflow_stmt = text(
            """
            SELECT project_id, data_category
            FROM crypto_data_snapshots
            GROUP BY project_id, data_category
            HAVING COUNT(*) > :max_rows
            """
        )
        result = await db.execute(overflow_stmt, {"max_rows": max_rows})
        pairs = result.fetchall()

        total_deleted = 0
        for project_id, data_category in pairs:
            # Delete rows outside the top-1000 newest (by fetched_at)
            del_stmt = text(
                """
                DELETE FROM crypto_data_snapshots
                WHERE id NOT IN (
                    SELECT id FROM crypto_data_snapshots
                    WHERE project_id = :project_id
                      AND data_category = :data_category
                    ORDER BY fetched_at DESC
                    LIMIT :max_rows
                )
                AND project_id = :project_id
                AND data_category = :data_category
                """
            )
            res = await db.execute(
                del_stmt,
                {
                    "project_id": project_id,
                    "data_category": data_category,
                    "max_rows": max_rows,
                },
            )
            total_deleted += res.rowcount

        # Commit unconditionally — even if `rowcount` reports 0 for some drivers,
        # actual rows may have been removed. Rolling back via exit-without-commit
        # would leave the DB in an inconsistent state.
        await db.commit()
        if total_deleted:
            logger.info(
                "CryptoCleanup: pruned %d excess snapshots across %d pairs",
                total_deleted,
                len(pairs),
            )


# ---------------------------------------------------------------------------
# Task 3: Orphaned-cache purge (Story 11.3)
# ---------------------------------------------------------------------------


# Idempotency lock — prevents concurrent execution if a worker restarts
# mid-task or beat re-enqueues. SET NX with a 2-hour TTL: long enough to cover
# any reasonable run, short enough that a crashed worker doesn't block the
# next scheduled run a week later.
_ORPHAN_LOCK_KEY = "celery:lock:cleanup_orphaned_snapshots"
_ORPHAN_LOCK_TTL_SECONDS = 7200  # 2h
# Soft limit on iterations — defensive cap so a runaway loop cannot churn
# forever (e.g., FK anomaly causing rowcount to keep returning >= batch_size).
_MAX_BATCH_ITERATIONS = 200  # 200 * 1000 = 200k orphans/run, sized for the worst legacy backlog.


@celery_app.task(
    name="crypto.cleanup_orphaned_snapshots",
    bind=True,
    max_retries=0,
    # Hard wall-clock guard: bigger than `expires` (which only stops *unstarted*
    # tasks). Inline guard prevents the task from holding row locks past the
    # weekly window if something pathological happens.
    time_limit=5400,  # 90 min hard
    soft_time_limit=4500,  # 75 min soft
)
def cleanup_orphaned_crypto_snapshots(self):
    """Weekly Sunday 4 AM UTC: delete snapshots linked to deleted search spaces."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_cleanup_orphaned())
    finally:
        loop.close()


async def _try_acquire_orphan_lock():
    """SET NX a Redis lock; return (acquired_bool, token, redis_client_or_None)."""
    from app.services.crypto_cache_lock import get_redis_client

    redis = get_redis_client()
    if redis is None:
        # No Redis: best-effort, allow the run. Single-worker deployments are
        # already serialised by Celery beat itself.
        return True, None, None
    token = str(uuid.uuid4())
    try:
        acquired = await redis.set(
            _ORPHAN_LOCK_KEY, token, nx=True, ex=_ORPHAN_LOCK_TTL_SECONDS
        )
        return bool(acquired), token, redis
    except Exception as exc:
        logger.warning("cleanup_orphaned_snapshots: lock acquire failed: %s", exc)
        return True, None, None


async def _release_orphan_lock(redis, token):
    """Release the lock only if we still own it (token-match via Lua)."""
    if redis is None or token is None:
        return
    release_script = (
        'if redis.call("get", KEYS[1]) == ARGV[1] then '
        'return redis.call("del", KEYS[1]) else return 0 end'
    )
    try:
        await redis.eval(release_script, 1, _ORPHAN_LOCK_KEY, token)
    except Exception as exc:
        logger.warning("cleanup_orphaned_snapshots: lock release failed: %s", exc)


def _emit_metric(payload: dict) -> None:
    """Write a single line of valid JSON to the metrics logger.

    Routed through `crypto.metrics` (a dedicated logger) so operators can
    attach a JSON-only formatter without affecting other Celery logs.
    """
    metric_logger.info(json.dumps(payload))


async def _async_cleanup_orphaned():
    """AC1-AC6: Purge orphaned snapshots in batches of 1000.

    Hardened (Round 2 review):
    - Idempotency lock via Redis SET NX (skip if another instance holds it)
    - Per-batch `statement_timeout` (60s) so a row-lock contention cannot hang
    - `status` field in metric line: completed | failed | skipped_locked
    - Hard iteration cap to prevent runaway loops
    """
    start_time = time.perf_counter()
    total_deleted = 0
    batch_size = 1000
    iterations = 0
    status = "completed"
    error_message: str | None = None

    acquired, lock_token, redis = await _try_acquire_orphan_lock()
    if not acquired:
        _emit_metric(
            {
                "task": "cleanup_orphaned_snapshots",
                "status": "skipped_locked",
                "deleted_count": 0,
                "duration_ms": 0,
                "reason": "another instance is running",
            }
        )
        return

    try:
        async with get_celery_session_maker()() as db:
            # Per-session statement timeout (PostgreSQL): if a single DELETE
            # batch hits row-lock contention or table-scan slowness, abort
            # and surface as a task failure rather than blocking forever.
            try:
                await db.execute(text("SET LOCAL statement_timeout = '60s'"))
            except Exception:
                # SQLite (tests) or non-Postgres backend — silently skip.
                pass

            while True:
                if iterations >= _MAX_BATCH_ITERATIONS:
                    status = "failed"
                    error_message = (
                        f"max batch iterations ({_MAX_BATCH_ITERATIONS}) exceeded"
                    )
                    logger.error(
                        "cleanup_orphaned_snapshots: %s — aborting", error_message
                    )
                    break
                iterations += 1

                # Delete snapshots where search_space_id exists but space is gone.
                # ORDER BY id ASC ensures forward progress; the inner LIMIT keeps
                # each transaction small to avoid long row-lock holds.
                del_stmt = text(
                    """
                    DELETE FROM crypto_data_snapshots
                    WHERE id IN (
                        SELECT id FROM crypto_data_snapshots
                        WHERE search_space_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM searchspaces
                              WHERE searchspaces.id = crypto_data_snapshots.search_space_id
                          )
                        ORDER BY id ASC
                        LIMIT :batch_size
                    )
                    """
                )
                result = await db.execute(del_stmt, {"batch_size": batch_size})
                count = result.rowcount
                total_deleted += count
                await db.commit()

                if count < batch_size:
                    break
    except Exception as exc:
        status = "failed"
        error_message = f"{type(exc).__name__}: {exc}"
        logger.exception("cleanup_orphaned_snapshots: aborted with exception")
        # Re-raise so Celery records the task failure for retry/alerting.
        raise
    finally:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        payload: dict = {
            "task": "cleanup_orphaned_snapshots",
            "status": status,
            "deleted_count": total_deleted,
            "duration_ms": duration_ms,
            "iterations": iterations,
        }
        if error_message:
            payload["error"] = error_message
        _emit_metric(payload)
        await _release_orphan_lock(redis, lock_token)
