from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from collections import defaultdict
from typing import Any

from app.celery_app import (
    celery_app,
)
from app.config import config
from app.db import (
    AuditEvent,
)

from ._helpers import (
    _CELERY_TASK_STALLED_SECONDS,
    _QUEUE_NAMES,
    _is_redis_broker,
    _maybe_async,
    _redis_queue_lengths,
    _redis_queue_stalled_and_throughput,
)

logger = logging.getLogger(__name__)


class QueueTelemetryMixin:
    async def get_celery_queue_stats(self) -> dict[str, Any]:
        """Return Celery queue lengths and worker telemetry.

        Uses Redis directly for queue lengths and Celery ``control.inspect``
        for worker/task metadata. Falls back to ``unavailable`` when the
        broker cannot be reached.
        """
        import redis.asyncio as aioredis

        try:
            inspect = celery_app.control.inspect(timeout=2.0)
            # ``control.inspect()`` calls are synchronous and block the event
            # loop; run them in a thread and unwrap any awaitable results.
            stats = await _maybe_async(await asyncio.to_thread(inspect.stats)) or {}
            active = await _maybe_async(await asyncio.to_thread(inspect.active)) or {}
            scheduled = (
                await _maybe_async(await asyncio.to_thread(inspect.scheduled)) or {}
            )
            reserved = (
                await _maybe_async(await asyncio.to_thread(inspect.reserved)) or {}
            )
            active_queues = (
                await _maybe_async(await asyncio.to_thread(inspect.active_queues)) or {}
            )
        except Exception as exc:  # Celery broker unready → degraded snapshot, not a 500
            logger.warning("Celery inspect failed: %s", exc)
            return {
                "status": "unavailable",
                "active_workers": 0,
                "queues": [],
            }

        worker_count = len(stats)

        # Aggregate tasks per queue from active/scheduled/reserved.
        per_queue_tasks: dict[str, int] = defaultdict(int)
        for source in (active, scheduled, reserved):
            for _worker, tasks in source.items():
                for task in tasks or []:
                    if isinstance(task, (list, tuple)):
                        task = task[0]
                    queue = (
                        task.get("delivery_info", {}).get("routing_key")
                        or task.get("properties", {}).get("routing_key")
                        or "unknown"
                    )
                    per_queue_tasks[queue] += 1

        # Discover queue names: hardcoded fallback + active queues + Redis keys.
        discovered_queues: set[str] = set(_QUEUE_NAMES)
        for queues_info in active_queues.values():
            for q in queues_info or []:
                name = q.get("name")
                if name:
                    discovered_queues.add(name)

        broker_url = config.CELERY_BROKER_URL or ""
        if _is_redis_broker(broker_url):
            try:
                redis_client = aioredis.from_url(broker_url, socket_connect_timeout=2)
                async for key in redis_client.scan_iter(match="celery*"):
                    discovered_queues.add(key.decode())
                await redis_client.aclose()
            except Exception as exc:  # Redis discovery best-effort; discovered set may stay empty
                logger.warning("Redis queue discovery failed: %s", exc)

        queue_names = sorted(discovered_queues)
        queue_lengths = await _redis_queue_lengths(queue_names)
        queue_stalled_throughput = await _redis_queue_stalled_and_throughput(
            queue_names
        )

        queues = []
        for name in queue_names:
            length = queue_lengths.get(name, 0)
            tasks = per_queue_tasks.get(name, 0)
            workers = sum(
                1
                for queues_info in active_queues.values()
                for q in (queues_info or [])
                if q.get("name") == name
            )
            status = "healthy"
            if length > 10000:
                status = "backed_up"
            elif length > 1000:
                status = "degraded"

            stalled_count, recent_throughput = queue_stalled_throughput.get(
                name, (0, 0)
            )

            queues.append(
                {
                    "name": name,
                    "length": length,
                    "workers": workers,
                    "throughput_per_min": recent_throughput
                    or tasks,  # fallback to active-task proxy
                    "stalled_count": stalled_count,
                    "status": status,
                }
            )

        overall = "healthy"
        if any(q["status"] == "backed_up" for q in queues):
            overall = "degraded"
        if worker_count == 0 or not queue_lengths:
            overall = "unavailable"

        return {
            "status": overall,
            "active_workers": worker_count,
            "queues": queues,
        }

    async def purge_dead_letter_queue(
        self,
        queue_name: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        """Purge stalled tasks from a Celery queue.

        Acquires a Redis lock, writes an ``AuditEvent``, and removes messages
        older than ``CELERY_TASK_STALLED_SECONDS`` from the Redis queue.
        """
        import redis.asyncio as aioredis

        if queue_name not in _QUEUE_NAMES:
            raise ValueError(f"Unknown queue: {queue_name}")

        # Idempotency key is for AuditEvent/client correlation only.
        idempotency_key = str(uuid.uuid4())
        # The lock is deterministic per queue so concurrent purges are rejected.
        lock_name = f"purge_dlq:{queue_name}"

        broker_url = config.CELERY_BROKER_URL or ""
        if not _is_redis_broker(broker_url):
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }

        try:
            redis_client = aioredis.from_url(broker_url, socket_connect_timeout=2)
        except Exception as exc:  # Redis connect failure → report zero purged with idempotency key
            logger.warning("Failed to connect to Redis for purge: %s", exc)
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }

        lock = redis_client.lock(lock_name, timeout=10)
        if not await lock.acquire(blocking=False):
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }

        try:
            now_wall = time.time()
            now_mono = time.monotonic_ns()
            threshold = _CELERY_TASK_STALLED_SECONDS
            purged = 0
            kept = 0

            # v1: read the whole queue, then atomically replace it with the
            # kept messages. There is a read-modify-write race with producers
            # pushing new messages between LRANGE and the pipeline; acceptable
            # for an emergency purge in v1.
            queue_len = int(await redis_client.llen(queue_name) or 0)
            messages = (
                await redis_client.lrange(queue_name, 0, queue_len - 1)
                if queue_len > 0
                else []
            )
            to_repush: list[bytes] = []

            for raw in messages:
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Malformed message - treat as stalled and purge
                    purged += 1
                    continue

                timestamps = payload.get("properties", {}).get("timestamps", {}) or {}
                sent_at = timestamps.get("sent")
                enqueued_ns = payload.get("headers", {}).get("nowing.enqueued_at_ns")

                stale = False
                if sent_at is not None:
                    # ``timestamps["sent"]`` is wall time, so compare with time.time().
                    try:
                        if now_wall - float(sent_at) > threshold:
                            stale = True
                    except (ValueError, TypeError) as exc:
                        logger.debug("Suppressed %r", exc)
                elif enqueued_ns is not None:
                    # ``nowing.enqueued_at_ns`` is set with time.monotonic_ns(),
                    # so compare with time.monotonic_ns().
                    try:
                        if (now_mono - int(enqueued_ns)) / 1e9 > threshold:
                            stale = True
                    except (ValueError, TypeError) as exc:
                        logger.debug("Suppressed %r", exc)

                if stale:
                    purged += 1
                    continue

                to_repush.append(raw)
                kept += 1

            # Only mutate when we are actually dropping messages; this avoids
            # the read-modify-write race for the common nothing-to-purge case.
            if purged > 0 or (queue_len > 0 and not to_repush):
                async with redis_client.pipeline(transaction=True) as pipe:
                    pipe.delete(queue_name)
                    if to_repush:
                        pipe.rpush(queue_name, *to_repush)
                    await pipe.execute()

            if actor_id:
                self.session.add(
                    AuditEvent(
                        action="telemetry.purge_dlq",
                        actor_id=actor_id,
                        diff_payload={"queue": queue_name, "count": purged},
                    )
                )
                await self.session.commit()

            return {
                "queue_name": queue_name,
                "purged_count": purged,
                "idempotency_key": idempotency_key,
            }
        except Exception as exc:  # purge failure → report zero purged with idempotency key, not a 500
            logger.exception("Failed to purge dead queue: %s", exc)
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }
        finally:
            with contextlib.suppress(Exception):
                await lock.release()
            await redis_client.aclose()
