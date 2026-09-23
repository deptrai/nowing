"""Celery task wrapper for the social stream consumer (Story 21.8b)."""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.celery_app import celery_app
from app.config import config
from app.tasks.celery_tasks import run_async_celery_task
from app.tasks.social_stream_worker import run_social_stream_consumer

logger = logging.getLogger(__name__)


@celery_app.task(
    name="process_social_stream",
    bind=True,
    default_retry_delay=30,
    max_retries=3,
)
def process_social_stream_task(self) -> int:
    """Celery task that consumes events from `stream:social:raw_posts`.

    The consumer uses Redis consumer groups to allow multiple workers to
    process messages in parallel. It creates `SocialPost` and `Lead` records,
    evaluates `AlertRule` matches, and ACKs or moves failed messages to DLQ.
    """

    async def _consume() -> int:
        redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
        try:
            return await run_social_stream_consumer(
                redis_client=redis_client,
                batch_size=10,
                block_ms=2000,
            )
        finally:
            try:
                await redis_client.aclose()
            except Exception as exc:  # best-effort redis client close; suppressed
                logger.debug("Suppressed %r", exc)

    try:
        return run_async_celery_task(_consume)
    except Exception as exc:  # task-level guard: retry-eligible failure → re-raise for celery retry
        # Retry on transient Redis or DB errors; permanent failures should land
        # in the dead-letter queue inside run_social_stream_consumer.
        raise self.retry(exc=exc) from exc
