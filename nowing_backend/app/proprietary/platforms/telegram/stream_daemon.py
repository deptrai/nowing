"""Telegram Realtime Stream Daemon & Event Processor (Story 22.3 / AC-3 / AD-5).

Handles Redis leader election ('telegram:daemon:leader'), pushes raw message events
to Redis Stream ('stream:telegram:raw_events'), and triggers real-time AlertRule evaluation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.proprietary.platforms.telegram.entity_extractor import TelegramEntityExtractor

logger = logging.getLogger(__name__)

REDIS_LEADER_KEY = "telegram:daemon:leader"
STREAM_TELEGRAM_RAW_EVENTS = "stream:telegram:raw_events"
LEADER_LOCK_TTL_SECONDS = 30


class TelegramStreamDaemon:
    """Singleton-guarded realtime Telegram stream listener."""

    def __init__(self, daemon_id: str, redis_client: Any = None):
        self.daemon_id = daemon_id
        self.redis_client = redis_client
        self.is_leader = False

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
        return self.is_leader

    async def handle_incoming_message(self, event_payload: dict[str, Any]) -> str | None:
        """Serialize and push new message event to Redis Stream."""
        if not self.redis_client:
            return None

        # Normalize message payload
        stream_data = {
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in event_payload.items()
        }
        res = await self.redis_client.xadd(STREAM_TELEGRAM_RAW_EVENTS, stream_data)
        return str(res) if res else None


async def process_telegram_stream_event(event: dict[str, Any]) -> None:
    """Process a single event from stream:telegram:raw_events and evaluate alert rules."""
    text = event.get("message_text", "")
    if "entities" not in event and text:
        event["entities"] = TelegramEntityExtractor.extract_entities(text)

    from app.alerts.engine.notify import evaluate_alert_rules

    # Evaluate against active AlertRule saved searches
    await evaluate_alert_rules(event)
