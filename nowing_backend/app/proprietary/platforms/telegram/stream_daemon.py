"""Telegram Realtime Stream Daemon & Event Processor (Story 22.3 / AC-3 / AD-5).

Handles Redis leader election ('telegram:daemon:leader'), pushes raw message events
to Redis Stream ('stream:telegram:raw_events'), and triggers real-time AlertRule evaluation.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.proprietary.platforms.telegram.entity_extractor import TelegramEntityExtractor

logger = logging.getLogger(__name__)

REDIS_LEADER_KEY = "telegram:daemon:leader"
STREAM_TELEGRAM_RAW_EVENTS = "stream:telegram:raw_events"
LEADER_LOCK_TTL_SECONDS = 30
HEARTBEAT_INTERVAL_SECONDS = 10
STREAM_MAX_LEN = 100_000

# Atomic release Lua script ensuring only lock owner can delete the leader key
RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Atomic renew Lua script
RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""


class TelegramStreamDaemon:
    """Singleton-guarded realtime Telegram stream listener."""

    def __init__(self, daemon_id: str, redis_client: Any = None):
        self.daemon_id = daemon_id
        self.redis_client = redis_client
        self.is_leader = False
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def try_acquire_leader(self) -> bool:
        """Attempt to acquire singleton leader lock in Redis."""
        if not self.redis_client:
            return False

        res = await self.redis_client.set(
            REDIS_LEADER_KEY,
            self.daemon_id,
            nx=True,
            ex=LEADER_LOCK_TTL_SECONDS,
        )
        self.is_leader = bool(res)
        if self.is_leader and not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        return self.is_leader

    async def renew_leader(self) -> bool:
        """Renew leadership lock TTL in Redis if still the owner."""
        if not self.redis_client or not self.is_leader:
            return False

        try:
            ttl_ms = LEADER_LOCK_TTL_SECONDS * 1000
            if hasattr(self.redis_client, "eval"):
                res = await self.redis_client.eval(
                    RENEW_LUA, 1, REDIS_LEADER_KEY, self.daemon_id, ttl_ms
                )
                return bool(res)
            # Fallback for simple mock clients
            val = await self.redis_client.get(REDIS_LEADER_KEY)
            if val == self.daemon_id:
                await self.redis_client.set(
                    REDIS_LEADER_KEY, self.daemon_id, ex=LEADER_LOCK_TTL_SECONDS
                )
                return True
        except Exception:
            logger.exception("Failed to renew leader lock for %s", self.daemon_id)
        return False

    async def release_leader(self) -> bool:
        """Release singleton leader lock upon graceful shutdown."""
        self.is_leader = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if not self.redis_client:
            return False

        try:
            if hasattr(self.redis_client, "eval"):
                res = await self.redis_client.eval(
                    RELEASE_LUA, 1, REDIS_LEADER_KEY, self.daemon_id
                )
                return bool(res)
            val = await self.redis_client.get(REDIS_LEADER_KEY)
            if val == self.daemon_id:
                await self.redis_client.delete(REDIS_LEADER_KEY)
                return True
        except Exception:
            logger.exception("Failed to release leader lock for %s", self.daemon_id)
        return False

    async def _heartbeat_loop(self) -> None:
        """Background coroutine renewing leader lease every 10s."""
        while self.is_leader:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                renewed = await self.renew_leader()
                if not renewed:
                    logger.warning(
                        "Lost leadership for daemon %s during heartbeat", self.daemon_id
                    )
                    self.is_leader = False
                    break
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in leader heartbeat loop")

    async def handle_incoming_message(
        self, event_payload: dict[str, Any]
    ) -> str | None:
        """Serialize and push new message event to Redis Stream."""
        if not self.redis_client:
            return None

        # Normalize message payload
        stream_data = {
            k: json.dumps(v)
            if isinstance(v, (dict, list))
            else ("" if v is None else str(v))
            for k, v in event_payload.items()
        }
        res = await self.redis_client.xadd(
            STREAM_TELEGRAM_RAW_EVENTS,
            stream_data,
            maxlen=STREAM_MAX_LEN,
            approximate=True,
        )
        return str(res) if res else None


async def process_telegram_stream_event(event: dict[str, Any]) -> None:
    """Process a single event from stream:telegram:raw_events and evaluate alert rules."""
    text = event.get("message_text", "")
    if "entities" not in event and text:
        event["entities"] = TelegramEntityExtractor.extract_entities(text)

    from app.alerts.engine.notify import evaluate_alert_rules

    # Evaluate against active AlertRule saved searches
    await evaluate_alert_rules(event)
