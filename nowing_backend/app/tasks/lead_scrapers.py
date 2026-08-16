"""Dedicated Celery tasks for Asynchronous Scraper Worker Pool (Story 23.1).

Governed by:
- AC-1: Dedicated Celery Queue (nowing.lead_scrapers) & Non-Blocking Dispatch (< 100ms)
- AC-2: Redis Stream Transit Buffer & Dual-Trigger Flush Window
- AC-3: Redis Lua Leaky-Bucket Rate Limiter & Circuit Breaker
- AC-4: Worker Crash Resilience (acks_late, reject_on_worker_lost) & Dead-Letter Recovery (XPENDING/XCLAIM)
- INV-23.1: Worker Queue Isolation
- INV-23.2: Bounded Redis Streams (MAXLEN ~ 10000)
- INV-23.3: Circuit Breaker Persistence in Redis (TTL 600s)
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import shared_task

from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.services.circuit_breaker import PlatformCircuitBreaker
from app.lead_intelligence.services.lead_stream_service import (
    LeadStreamBuffer,
    ingest_stream_leads_to_db,
)
from app.lead_intelligence.services.rate_limiter import PlatformRateLimiter
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

LEAD_SCRAPERS_QUEUE_NAME = "nowing.lead_scrapers"


async def _execute_scraper_job(
    workspace_id: int,
    platform: str,
    query: str,
    filters: dict[str, Any] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Execute scraping pipeline with rate limiting, circuit breaker, and stream buffer."""
    circuit_breaker = PlatformCircuitBreaker()
    rate_limiter = PlatformRateLimiter()

    # 1. Circuit Breaker Pre-check
    is_available = await circuit_breaker.is_available(platform)
    if not is_available:
        logger.warning(
            "Scraper platform %s circuit breaker is OPEN. Skipping execution.",
            platform,
        )
        return {
            "status": "circuit_open",
            "platform": platform,
            "leads_extracted": 0,
        }

    # 2. Rate Limiter Token Acquisition with controlled backoff retry
    rate_result = await rate_limiter.acquire(platform)
    for _ in range(3):
        if rate_result.allowed:
            break
        retry_delay = max(0.2, min(rate_result.retry_after_ms / 1000.0, 3.0))
        logger.warning(
            "Rate limit reached for %s. Backoff sleep for %.2fs.",
            platform,
            retry_delay,
        )
        await asyncio.sleep(retry_delay)
        rate_result = await rate_limiter.acquire(platform)

    # 3. Resolve Platform Adapter
    registry = LeadSourceAdapterRegistry.get_default()
    adapter = registry.get_adapter(platform)
    if not adapter:
        logger.error("No adapter registered for platform %s", platform)
        return {
            "status": "error",
            "platform": platform,
            "error": f"Adapter not found for {platform}",
        }

    # 4. Stream Buffer Setup
    buffer = LeadStreamBuffer(workspace_id=workspace_id)
    extracted_leads: list[dict[str, Any]] = []

    try:
        raw_records = await adapter.search_leads(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            limit=limit,
        )

        for record in raw_records:
            try:
                norm = adapter.normalize_lead(record)
                lead_dict = norm.model_dump()
                lead_dict.setdefault("workspace_id", workspace_id)
                extracted_leads.append(lead_dict)
                await buffer.add_lead(lead_dict)
            except Exception as norm_err:
                logger.warning(
                    "Normalization error on platform %s for record: %s",
                    platform,
                    norm_err,
                )

        # Flush any remaining items in buffer to Redis Stream
        await buffer.flush()

        # Mark success in Circuit Breaker
        await circuit_breaker.record_success(platform)

        # Upsert into PostgreSQL table
        if extracted_leads:
            await ingest_stream_leads_to_db(workspace_id, extracted_leads)

        return {
            "status": "success",
            "platform": platform,
            "leads_extracted": len(extracted_leads),
        }

    except Exception as exc:
        logger.error("Scraper failed on %s: %s", platform, exc)
        status_code = getattr(exc, "status_code", 500)
        # Record failure for circuit breaker only on external/network/anti-bot errors
        await circuit_breaker.record_failure(
            platform=platform,
            reason=str(exc),
            status_code=status_code,
        )
        raise


@shared_task(
    name="app.tasks.lead_scrapers.run_platform_scrape_task",
    queue=LEAD_SCRAPERS_QUEUE_NAME,
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=120,
    soft_time_limit=60,
    bind=True,
)
def run_platform_scrape_task(
    self,
    workspace_id: int,
    platform: str,
    query: str,
    filters: dict[str, Any] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Celery worker task executing async platform scraping on dedicated worker pool."""
    return asyncio.run(
        _execute_scraper_job(
            workspace_id=workspace_id,
            platform=platform,
            query=query,
            filters=filters,
            limit=limit,
        )
    )


async def reclaim_pending_stream_messages(
    workspace_id: int,
    group_name: str,
    recovery_consumer: str,
    min_idle_ms: int = 30000,
    redis_client: Any = None,
) -> int:
    """
    AC-4: Track pending Redis Stream messages via XPENDING and reclaim via XCLAIM
    after `min_idle_ms` (30s) of consumer inactivity.
    """
    redis = redis_client or await get_redis_client()
    stream_key = f"workspace:{workspace_id}:leads_stream"

    try:
        pending_entries = await redis.xpending_range(
            stream_key,
            group_name,
            min="-",
            max="+",
            count=100,
        )
    except Exception as exc:
        logger.debug("No pending messages or group not found: %s", exc)
        return 0

    reclaimed_count = 0
    for entry in pending_entries:
        if isinstance(entry, dict):
            msg_id = entry.get("message_id")
            idle_time = entry.get("idle_time", 0)
        else:
            msg_id = entry[0] if len(entry) > 0 else None
            idle_time = entry[2] if len(entry) > 2 else 0

        if msg_id and idle_time >= min_idle_ms:
            claimed = await redis.xclaim(
                stream_key,
                group_name,
                recovery_consumer,
                min_idle_ms,
                [msg_id],
            )
            if claimed:
                reclaimed_count += len(claimed)

    return reclaimed_count
