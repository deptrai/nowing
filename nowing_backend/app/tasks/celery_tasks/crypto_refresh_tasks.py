"""Celery tasks for proactive crypto data cache refresh and cleanup.

Two tasks:
  - refresh_popular_crypto_data: every 30 min — pre-warm tokens expiring soon
  - cleanup_expired_crypto_snapshots: daily 3 AM UTC — prune old rows
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text

from app.celery_app import celery_app
from app.db import CryptoDataSnapshot
from app.tasks.celery_tasks import get_celery_session_maker

logger = logging.getLogger(__name__)


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
    """Call the tool function directly (no agent context) to refresh a single snapshot."""
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
        import json as _json
        try:
            result = _json.loads(result)
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

        if total_deleted:
            await db.commit()
            logger.info("CryptoCleanup: pruned %d excess snapshots across %d pairs", total_deleted, len(pairs))
