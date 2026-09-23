"""Celery task wrappers for the proactive intent signal radar (Story 37.1).

Two Beat-driven tasks:

- ``scan_high_intent_companies_periodic`` (every 6h): hiring-surge +
  newly-incorporated tax-code scan persisting ``SignalEvent`` rows at
  ``intent_score >= 0.75`` (AC-1), with AD-115 budget guardrails.
- ``process_telegram_intent_stream`` (every 30s): short-lived consumer on
  ``stream:telegram:raw_events`` running the in-memory Aho-Corasick
  purchase-intent pre-filter before regex extraction (AC-2/AC-3).
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.celery_app import celery_app
from app.config import config
from app.lead_intelligence.signals.radar import (
    run_periodic_signal_scan,
    run_telegram_intent_consumer,
)
from app.tasks.celery_tasks import run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(
    name="scan_high_intent_companies_periodic",
    bind=True,
    default_retry_delay=300,
    max_retries=2,
)
def scan_high_intent_companies_periodic_task(self) -> dict:
    """AC-1: every-six-hours high-intent company scan across workspaces."""

    async def _scan() -> dict:
        redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
        try:
            return await run_periodic_signal_scan(redis_client=redis_client)
        finally:
            try:
                await redis_client.aclose()
            except Exception as exc:  # best-effort redis client close; suppressed
                logger.debug("Suppressed %r", exc)

    try:
        return run_async_celery_task(_scan)
    except (
        Exception
    ) as exc:  # task-level guard: retry-eligible failure → re-raise for celery retry
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="process_telegram_intent_stream",
    bind=True,
    default_retry_delay=30,
    max_retries=3,
)
def process_telegram_intent_stream_task(self) -> int:
    """AC-2/AC-3: consume `stream:telegram:raw_events` for purchase intent.

    Short-lived batch consumer — Beat re-enqueues it every 30s. Messages that
    fail processing land in ``stream:telegram:intent_dlq``.
    """

    async def _consume() -> int:
        redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
        try:
            # 100 msgs/loop x 3 loops per 30s tick — batch_size=10 would cap
            # throughput at ~0.33 msg/s and silently grow the backlog.
            return await run_telegram_intent_consumer(
                redis_client=redis_client,
                batch_size=100,
                block_ms=2000,
                max_loops=3,
            )
        finally:
            try:
                await redis_client.aclose()
            except Exception as exc:  # best-effort redis client close; suppressed
                logger.debug("Suppressed %r", exc)

    try:
        return run_async_celery_task(_consume)
    except (
        Exception
    ) as exc:  # task-level guard: retry-eligible failure → re-raise for celery retry
        raise self.retry(exc=exc) from exc
