"""Outbound Trigger Engine: Speed-to-Lead & Hiring Radar (Story 38.7).

Automatically triggers outbound Voice AI SDR calls from real-time events:
1. Speed-to-Lead (< 5 min): Listens to Redis stream `stream:prospect:engagement`
   (Story 37.6). If a prospect views a Mini-Pitch portal for >= 45 seconds,
   triggers a voice outreach call immediately (delay=0).
2. Hiring Radar: Evaluates SignalEvent intent signals (Story 37.1). If a
   hiring expansion is detected with confidence >= 0.75, enrolls the lead
   into a voice sequence step.

Constraints:
- Submits dispatch jobs via Celery task `dispatch_voice_call_task` or Sequencer
  enrollment — no independent event loops or schedulers.
- Reuses Redis client from app.lead_intelligence.dnc.service.get_redis().
- Enforces min view duration (45s) and min confidence (0.75) thresholds.
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# Speed-to-Lead threshold: viewing Mini-Pitch for >= 45s indicates high buying intent
_SPEED_TO_LEAD_MIN_VIEW_SECONDS = 45.0

# Hiring Radar threshold: intent signal confidence must meet 0.75 bar
_HIRING_RADAR_MIN_CONFIDENCE = 0.75


@dataclass(frozen=True)
class TriggerResult:
    """Outcome of an outbound trigger evaluation."""

    triggered: bool
    trigger_type: str  # 'speed_to_lead', 'hiring_radar', 'none'
    reason: str
    workspace_id: int | None = None
    lead_id: UUID | None = None
    phone_e164: str | None = None
    task_id: str | None = None


class OutboundTriggerEngine:
    """Evaluates real-time events and dispatches Voice AI SDR calls."""

    def __init__(
        self,
        *,
        speed_to_lead_min_seconds: float = _SPEED_TO_LEAD_MIN_VIEW_SECONDS,
        hiring_radar_min_confidence: float = _HIRING_RADAR_MIN_CONFIDENCE,
    ) -> None:
        self.speed_to_lead_min_seconds = speed_to_lead_min_seconds
        self.hiring_radar_min_confidence = hiring_radar_min_confidence

    async def handle_prospect_engagement(
        self,
        event_data: dict[str, Any],
    ) -> TriggerResult:
        """Evaluate pitch portal engagement from `stream:prospect:engagement`.

        Trigger criteria:
        - `view_duration_seconds >= 45.0`
        - `phone_e164` present and non-empty
        - `workspace_id` present
        """
        duration = float(event_data.get("view_duration_seconds", 0.0))
        workspace_id = event_data.get("workspace_id")
        phone_e164 = event_data.get("phone_e164") or event_data.get("phone")
        lead_id_raw = event_data.get("lead_id")

        if duration < self.speed_to_lead_min_seconds:
            return TriggerResult(
                triggered=False,
                trigger_type="speed_to_lead",
                reason=(
                    f"View duration {duration:.1f}s is below threshold "
                    f"{self.speed_to_lead_min_seconds:.1f}s"
                ),
            )

        if not phone_e164 or not str(phone_e164).strip():
            return TriggerResult(
                triggered=False,
                trigger_type="speed_to_lead",
                reason="Prospect has no phone number on record",
            )

        if not workspace_id:
            return TriggerResult(
                triggered=False,
                trigger_type="speed_to_lead",
                reason="Event missing workspace_id",
            )

        lead_id = UUID(str(lead_id_raw)) if lead_id_raw else None

        # Queue asynchronous voice dispatch via Celery
        from app.tasks.celery_tasks.voice_tasks import dispatch_voice_call_task

        async_result = dispatch_voice_call_task.delay(
            workspace_id=int(workspace_id),
            phone_e164=str(phone_e164),
            lead_id=str(lead_id) if lead_id else None,
            user_id=str(event_data.get("user_id"))
            if event_data.get("user_id")
            else None,
        )

        task_id = getattr(async_result, "id", None) or "dispatched_async"
        logger.info(
            "[SpeedToLead] Triggered Voice SDR call ws=%s phone=%s duration=%.1fs task=%s",
            workspace_id,
            str(phone_e164)[:6] + "...",
            duration,
            task_id,
        )

        return TriggerResult(
            triggered=True,
            trigger_type="speed_to_lead",
            reason=f"High-intent engagement ({duration:.1f}s >= {self.speed_to_lead_min_seconds:.1f}s)",
            workspace_id=int(workspace_id),
            lead_id=lead_id,
            phone_e164=str(phone_e164),
            task_id=task_id,
        )

    async def handle_hiring_radar_signal(
        self,
        signal_event: dict[str, Any],
    ) -> TriggerResult:
        """Evaluate Intent Radar hiring signal (Story 37.1).

        Trigger criteria:
        - `signal_type in ('hiring_expansion', 'job_posting_surge', 'key_hire')`
        - `confidence >= 0.75`
        - `phone_e164` present
        - `workspace_id` present
        """
        signal_type = str(signal_event.get("signal_type", ""))
        confidence = float(signal_event.get("confidence", 0.0))
        workspace_id = signal_event.get("workspace_id")
        phone_e164 = signal_event.get("phone_e164") or signal_event.get("phone")
        lead_id_raw = signal_event.get("lead_id")

        supported_signals = {
            "hiring_expansion",
            "job_posting_surge",
            "key_hire",
            "intent_radar",
        }
        if signal_type not in supported_signals:
            return TriggerResult(
                triggered=False,
                trigger_type="hiring_radar",
                reason=f"Signal type {signal_type!r} is not an outbound trigger type",
            )

        if confidence < self.hiring_radar_min_confidence:
            return TriggerResult(
                triggered=False,
                trigger_type="hiring_radar",
                reason=(
                    f"Confidence {confidence:.2f} is below threshold "
                    f"{self.hiring_radar_min_confidence:.2f}"
                ),
            )

        if not phone_e164 or not str(phone_e164).strip():
            return TriggerResult(
                triggered=False,
                trigger_type="hiring_radar",
                reason="Target lead has no phone number on record",
            )

        if not workspace_id:
            return TriggerResult(
                triggered=False,
                trigger_type="hiring_radar",
                reason="Signal missing workspace_id",
            )

        lead_id = UUID(str(lead_id_raw)) if lead_id_raw else None

        from app.tasks.celery_tasks.voice_tasks import dispatch_voice_call_task

        async_result = dispatch_voice_call_task.delay(
            workspace_id=int(workspace_id),
            phone_e164=str(phone_e164),
            lead_id=str(lead_id) if lead_id else None,
            user_id=str(signal_event.get("user_id"))
            if signal_event.get("user_id")
            else None,
        )

        task_id = getattr(async_result, "id", None) or "dispatched_async"
        logger.info(
            "[HiringRadar] Triggered Voice SDR call ws=%s signal=%s conf=%.2f task=%s",
            workspace_id,
            signal_type,
            confidence,
            task_id,
        )

        return TriggerResult(
            triggered=True,
            trigger_type="hiring_radar",
            reason=f"Hiring expansion verified (conf={confidence:.2f})",
            workspace_id=int(workspace_id),
            lead_id=lead_id,
            phone_e164=str(phone_e164),
            task_id=task_id,
        )


STREAM_PROSPECT_ENGAGEMENT = "stream:prospect:engagement"
PROSPECT_ENGAGEMENT_CONSUMER_GROUP = "prospect_engagement_voice_trigger"


def _parse_stream_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract event dict from raw Redis stream entry fields."""
    if "payload" in raw_payload:
        try:
            parsed = json.loads(raw_payload["payload"])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    if "data" in raw_payload:
        try:
            parsed = json.loads(raw_payload["data"])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return raw_payload


async def handle_prospect_engagement(
    event_data: dict[str, Any],
    *,
    engine: OutboundTriggerEngine | None = None,
) -> TriggerResult:
    """Convenience module function evaluating pitch portal engagement."""
    active_engine = engine or OutboundTriggerEngine()
    return await active_engine.handle_prospect_engagement(event_data)


async def consume_prospect_engagement_stream(
    redis_client: Any | None = None,
    consumer_name: str | None = None,
    batch_size: int = 50,
    block_ms: int = 1000,
    engine: OutboundTriggerEngine | None = None,
) -> int:
    """Consume a bounded batch of engagement events from Redis stream (AI-38.2).

    Idempotently ensures consumer group exists, reads up to `batch_size` events via
    XREADGROUP, evaluates each via `handle_prospect_engagement`, and XACKs on success.
    Per-message failures are logged and left unacknowledged.
    """
    created_locally = False
    if redis_client is None:
        import redis.asyncio as aioredis

        from app.config import config

        if not getattr(config, "REDIS_APP_URL", None):
            logger.info(
                "REDIS_APP_URL not configured; skipping engagement stream consume"
            )
            return 0
        redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
        created_locally = True

    consumer_name = consumer_name or "voice_trigger_worker"

    try:
        try:
            await redis_client.xgroup_create(
                name=STREAM_PROSPECT_ENGAGEMENT,
                groupname=PROSPECT_ENGAGEMENT_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc).upper():
                logger.warning(
                    "Failed to create consumer group %s for stream %s: %s",
                    PROSPECT_ENGAGEMENT_CONSUMER_GROUP,
                    STREAM_PROSPECT_ENGAGEMENT,
                    exc,
                )

        count = max(1, min(batch_size, 50))
        entries = None
        try:
            entries = await redis_client.xreadgroup(
                groupname=PROSPECT_ENGAGEMENT_CONSUMER_GROUP,
                consumername=consumer_name,
                streams={STREAM_PROSPECT_ENGAGEMENT: ">"},
                count=count,
                block=block_ms,
            )
        except Exception as exc:
            logger.error("Error reading %s stream: %s", STREAM_PROSPECT_ENGAGEMENT, exc)
            return 0

        if not entries:
            return 0

        processed = 0
        trigger_engine = engine or OutboundTriggerEngine()

        for _stream, messages in entries:
            for msg_id, raw_fields in messages:
                try:
                    event_data = (
                        _parse_stream_payload(raw_fields)
                        if isinstance(raw_fields, dict)
                        else {}
                    )
                    await trigger_engine.handle_prospect_engagement(event_data)
                    await redis_client.xack(
                        STREAM_PROSPECT_ENGAGEMENT,
                        PROSPECT_ENGAGEMENT_CONSUMER_GROUP,
                        msg_id,
                    )
                    processed += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to process engagement event %s: %s",
                        msg_id,
                        exc,
                    )

        return processed
    finally:
        if created_locally:
            with contextlib.suppress(Exception):
                await redis_client.aclose()
