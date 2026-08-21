"""Inbound Message Debounce Service (INV-24.7).

Aggregates rapid burst messages from the same sender within a 3s sliding window
before dispatching to LLM Auto-Reply processing.
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

from app.redis_client import get_redis_client as _get_shared_redis_client

logger = logging.getLogger(__name__)


class InboundDebounceService:
    """Buffers and aggregates rapid-fire inbound messages from external channels."""

    def __init__(self, redis_client=None, debounce_window_seconds: int = 3):
        self._redis = redis_client
        self.debounce_window = debounce_window_seconds

    async def _redis_client(self):
        if self._redis is None:
            self._redis = await _get_shared_redis_client()
        return self._redis

    def _buffer_key(self, channel: str, sender_id: str) -> str:
        return f"inbound_debounce:{channel}:{sender_id}"

    async def buffer_inbound_message(
        self,
        channel: str,
        sender_id: str,
        text: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Pushes a message chunk to the debounce buffer and refreshes the timer."""
        clean_text = (text or "").strip()
        if not clean_text:
            return False

        key = self._buffer_key(channel, sender_id)
        data = {
            "text": clean_text,
            "payload": payload or {},
        }
        # ponytail: default=str coerces unserializable values instead of raising.
        encoded = json.dumps(data, ensure_ascii=False, default=str)
        redis = await self._redis_client()
        async with redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, encoded)
            pipe.expire(key, self.debounce_window + 5)
            await pipe.execute()

        # Schedule the 3s debounce flush worker if caller provided routing context.
        workspace_id = (payload or {}).get("workspace_id")
        thread_id = (payload or {}).get("thread_id")
        account_id = (payload or {}).get("account_id")
        binding_id = (payload or {}).get("binding_id")
        if workspace_id and thread_id and account_id and binding_id:
            try:
                from app.celery_app import celery_app

                celery_app.send_task(
                    "gateway.process_auto_reply_buffer",
                    args=(channel, sender_id, workspace_id, thread_id, account_id, binding_id),
                    countdown=self.debounce_window,
                )
            except Exception as e:
                logger.warning("Failed to schedule auto-reply buffer worker: %s", e)
        return True

    async def flush_and_aggregate_messages(self, channel: str, sender_id: str) -> str:
        """Reads all buffered messages, concatenates them into a single string, and clears the buffer atomically."""
        key = self._buffer_key(channel, sender_id)
        lock_key = f"{key}:lock"
        redis = await self._redis_client()

        # Distributed lock to prevent double-processing across workers.
        lock_acquired = await redis.set(lock_key, "1", nx=True, ex=10)
        if not lock_acquired:
            logger.debug("Debounce flush already in progress for %s:%s", channel, sender_id)
            return ""

        try:
            # Atomic LRANGE + DEL Lua script to prevent dropped messages.
            lua_script = """
            local items = redis.call('LRANGE', KEYS[1], 0, -1)
            redis.call('DEL', KEYS[1])
            return items
            """
            try:
                res = await redis.eval(lua_script, 1, key)
            except Exception as e:
                logger.error("Lua eval failed for debounce buffer %s: %s", key, e)
                return ""

            raw_items = res if isinstance(res, (list, tuple)) else []

            if not raw_items:
                return ""

            messages: list[str] = []
            for raw in raw_items:
                if raw is None:
                    continue
                try:
                    decoded = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                    # Handle plain text vs JSON object
                    if decoded.startswith("{"):
                        parsed = json.loads(decoded)
                        txt = parsed.get("text", "")
                    else:
                        txt = decoded
                    if txt:
                        messages.append(txt)
                except Exception as e:
                    logger.warning("Failed to decode buffered inbound message: %s", e)
                    with contextlib.suppress(Exception):
                        if isinstance(raw, (bytes, bytearray)):
                            messages.append(raw.decode("utf-8", errors="ignore"))
                        else:
                            messages.append(str(raw))

            return "\n".join(messages).strip()
        finally:
            with contextlib.suppress(Exception):
                await redis.delete(lock_key)
