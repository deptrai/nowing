"""Redis-backed ``RunEventBus`` for multi-replica deployments.

This mirrors the in-memory :class:`app.capabilities.core.events.RunEventBus`
interface using Redis pub/sub. Events are JSON-encoded and published to a per-run
channel ``nowing:run:{run_id}``. A single async listener per process fans
received messages into the local ``asyncio.Queue`` s of open SSE connections.

All public methods are synchronous to match the existing interface, but they
schedule Redis I/O on the running event loop. Callers are always inside the
async API event loop.

ponytail: pub/sub is ephemeral. A subscriber that starts after an event is
published cannot replay that event from the bus. ``stream_run_events`` falls back
to the ``runs`` row snapshot when the run has already finished.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import deque
from collections.abc import Iterable
from typing import Any

from app.config import config
from app.observability import metrics

logger = logging.getLogger(__name__)


def _channel(run_id: str) -> str:
    return f"nowing:run:{run_id}"


class RedisRunEventBus:
    """Fan-out of per-run progress events across processes via Redis pub/sub."""

    def __init__(
        self,
        *,
        buffer_size: int = 500,
        subscriber_queue_size: int = 1000,
    ) -> None:
        self._buffer_size = buffer_size
        self._subscriber_queue_size = subscriber_queue_size
        self._buffers: dict[str, deque[dict[str, Any]]] = {}
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._redis: Any | None = None
        self._pubsub: Any | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._ensure_task: asyncio.Task[None] | None = None
        self._listener_lock = asyncio.Lock()

    # -- Redis client ----------------------------------------------------

    def _client(self) -> Any:
        if self._redis is None:
            from redis import asyncio as aioredis

            self._redis = aioredis.from_url(
                config.REDIS_APP_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30,
            )
        return self._redis

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            # Tests or non-async contexts should never reach here, but a
            # fallback is safer than a hard crash.
            return asyncio.get_event_loop_policy().get_event_loop()

    # -- listener lifecycle ----------------------------------------------

    def _log_task_exception(self, task: asyncio.Task[Any]) -> None:
        """Log exceptions from fire-and-forget tasks to avoid asyncio swallowing them."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("run_event_bus background task %r failed", task.get_name())

    def _fire(self, name: str, coro: Any) -> None:
        """Schedule a fire-and-forget coroutine with exception logging."""
        task = self._get_loop().create_task(coro, name=name)
        task.add_done_callback(self._log_task_exception)

    def _ensure_listener(self) -> None:
        async def _start() -> None:
            async with self._listener_lock:
                if self._listener_task is not None and not self._listener_task.done():
                    return

                if self._pubsub is not None:
                    with contextlib.suppress(Exception):
                        await self._pubsub.close()
                self._pubsub = self._client().pubsub()
                # Re-subscribe to every channel that already has a subscriber.
                channels = [
                    _channel(rid) for rid, subs in self._subscribers.items() if subs
                ]
                if channels:
                    await self._pubsub.subscribe(*channels)
                self._listener_task = asyncio.create_task(
                    self._listener(),
                    name="run_event_bus_redis_listener",
                )

        if self._ensure_task is not None and not self._ensure_task.done():
            with contextlib.suppress(Exception):
                self._ensure_task.cancel()
        self._ensure_task = self._get_loop().create_task(_start())
        self._ensure_task.add_done_callback(self._log_task_exception)

    async def _handle_listener_error(self) -> None:
        """Close the broken pub/sub, back off, and schedule a restart."""
        async with self._listener_lock:
            pubsub = self._pubsub
            self._pubsub = None
            self._listener_task = None
            with contextlib.suppress(Exception):
                await pubsub.close()
        await asyncio.sleep(1.0)
        self._ensure_listener()

    async def _listener(self) -> None:
        """Forward Redis pub/sub messages to local queues."""
        while self._pubsub is not None:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
            except Exception:
                logger.exception("run_event_bus redis listener error")
                await self._handle_listener_error()
                return
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            run_id = _run_id_from_channel(message.get("channel", ""))
            if not run_id:
                continue
            try:
                event = json.loads(message["data"])
            except json.JSONDecodeError:
                logger.warning(
                    "run_event_bus redis listener: invalid json on channel %s",
                    message.get("channel"),
                )
                continue
            buffer = self._buffers.setdefault(run_id, deque(maxlen=self._buffer_size))
            buffer.append(event)
            for queue in list(self._subscribers.get(run_id, ())):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        "run %s: subscriber queue full, dropping event", run_id
                    )
                    metrics.record_run_event_bus_dropped(reason="queue_full")

    def _subscribe_channel(self, run_id: str) -> None:
        async def _sub() -> None:
            if self._pubsub is None:
                return
            channel = _channel(run_id)
            try:
                await asyncio.wait_for(self._pubsub.subscribe(channel), timeout=5.0)
            except Exception:
                logger.warning("run %s: redis subscribe failed", run_id, exc_info=True)

        self._ensure_listener()
        self._fire(f"run_event_bus_subscribe:{run_id}", _sub())

    def _unsubscribe_channel(self, run_id: str) -> None:
        async def _unsub() -> None:
            if self._pubsub is None:
                return
            channel = _channel(run_id)
            try:
                await asyncio.wait_for(self._pubsub.unsubscribe(channel), timeout=5.0)
            except Exception:
                logger.warning(
                    "run %s: redis unsubscribe failed", run_id, exc_info=True
                )
            if not any(subs for subs in self._subscribers.values()):
                await self._stop_listener()

        self._fire(f"run_event_bus_unsubscribe:{run_id}", _unsub())

    async def _stop_listener(self) -> None:
        async with self._listener_lock:
            if self._listener_task is not None:
                self._listener_task.cancel()
                with contextlib.suppress(Exception):
                    await self._listener_task
                self._listener_task = None
            if self._pubsub is not None:
                with contextlib.suppress(Exception):
                    await self._pubsub.close()
                self._pubsub = None

    # -- task registry ---------------------------------------------------

    def register_task(self, run_id: str, task: asyncio.Task[Any]) -> None:
        self._tasks[run_id] = task

    def get_task(self, run_id: str) -> asyncio.Task[Any] | None:
        return self._tasks.get(run_id)

    # -- publish / subscribe ---------------------------------------------

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        """Publish an event to local subscribers and the Redis channel."""
        # Local buffer for replay in this process.
        buffer = self._buffers.setdefault(run_id, deque(maxlen=self._buffer_size))
        buffer.append(event)

        # Local fan-out is synchronous so SSE clients in the same process see
        # events immediately.
        for queue in list(self._subscribers.get(run_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("run %s: subscriber queue full, dropping event", run_id)
                metrics.record_run_event_bus_dropped(reason="queue_full")

        # Cross-replica fan-out through Redis.
        async def _pub() -> None:
            client = self._client()
            payload = json.dumps(event)
            channel = _channel(run_id)
            for attempt in range(2):
                try:
                    await asyncio.wait_for(
                        client.publish(channel, payload), timeout=5.0
                    )
                    return
                except TimeoutError:
                    logger.warning(
                        "run %s: redis publish timed out (attempt %d/2)",
                        run_id,
                        attempt + 1,
                    )
                except Exception:
                    logger.warning(
                        "run %s: redis publish failed (attempt %d/2)",
                        run_id,
                        attempt + 1,
                        exc_info=True,
                    )

        self._fire(f"run_event_bus_publish:{run_id}", _pub())

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._subscriber_queue_size
        )
        self._subscribers.setdefault(run_id, set()).add(queue)
        self._subscribe_channel(run_id)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._subscribers.get(run_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(run_id, None)
            self._unsubscribe_channel(run_id)

    def replay(self, run_id: str) -> Iterable[dict[str, Any]]:
        return list(self._buffers.get(run_id, ()))

    def close(self, run_id: str) -> None:
        """Drop all state for a finished run."""
        self._buffers.pop(run_id, None)
        self._subscribers.pop(run_id, None)
        self._tasks.pop(run_id, None)
        self._unsubscribe_channel(run_id)


def _run_id_from_channel(channel: str) -> str:
    """Reverse ``_channel(run_id)``: strip the ``nowing:run:`` prefix."""
    prefix = "nowing:run:"
    if channel.startswith(prefix):
        return channel[len(prefix) :]
    return ""
