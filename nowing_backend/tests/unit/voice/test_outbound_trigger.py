"""Unit tests for OutboundTriggerEngine (Story 38.7 Speed-to-Lead & Hiring Radar)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.voice.outbound_trigger import (
    PROSPECT_ENGAGEMENT_CONSUMER_GROUP,
    STREAM_PROSPECT_ENGAGEMENT,
    OutboundTriggerEngine,
    consume_prospect_engagement_stream,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def engine():
    return OutboundTriggerEngine(
        speed_to_lead_min_seconds=45.0,
        hiring_radar_min_confidence=0.75,
    )


class TestSpeedToLead:
    """Prospect engagement on Mini-Pitch portal >= 45s triggers Voice SDR call."""

    async def test_duration_above_45s_triggers_call(
        self, engine: OutboundTriggerEngine
    ):
        lead_id = uuid4()
        event_data = {
            "workspace_id": 15,
            "lead_id": str(lead_id),
            "phone_e164": "+84901234567",
            "view_duration_seconds": 52.0,
        }

        mock_celery_task = MagicMock()
        mock_celery_task.delay.return_value.id = "celery_task_123"

        with patch(
            "app.tasks.celery_tasks.voice_tasks.dispatch_voice_call_task",
            mock_celery_task,
        ):
            res = await engine.handle_prospect_engagement(event_data)

        assert res.triggered is True
        assert res.trigger_type == "speed_to_lead"
        assert res.workspace_id == 15
        assert res.phone_e164 == "+84901234567"
        assert res.task_id == "celery_task_123"
        mock_celery_task.delay.assert_called_once_with(
            workspace_id=15,
            phone_e164="+84901234567",
            lead_id=str(lead_id),
            user_id=None,
        )

    async def test_duration_below_45s_is_ignored(self, engine: OutboundTriggerEngine):
        event_data = {
            "workspace_id": 15,
            "phone_e164": "+84901234567",
            "view_duration_seconds": 20.0,
        }

        res = await engine.handle_prospect_engagement(event_data)
        assert res.triggered is False
        assert "below threshold" in res.reason

    async def test_missing_phone_is_ignored(self, engine: OutboundTriggerEngine):
        event_data = {
            "workspace_id": 15,
            "phone_e164": None,
            "view_duration_seconds": 60.0,
        }

        res = await engine.handle_prospect_engagement(event_data)
        assert res.triggered is False
        assert "no phone" in res.reason.lower()

    async def test_missing_workspace_id_is_ignored(self, engine: OutboundTriggerEngine):
        event_data = {
            "workspace_id": None,
            "phone_e164": "+84901234567",
            "view_duration_seconds": 60.0,
        }

        res = await engine.handle_prospect_engagement(event_data)
        assert res.triggered is False
        assert "missing workspace_id" in res.reason


class TestHiringRadar:
    """Intent Radar hiring signal with confidence >= 0.75 triggers Voice SDR call."""

    async def test_high_confidence_hiring_signal_triggers_call(
        self, engine: OutboundTriggerEngine
    ):
        lead_id = uuid4()
        signal_event = {
            "workspace_id": 15,
            "lead_id": str(lead_id),
            "phone_e164": "+842871099999",
            "signal_type": "hiring_expansion",
            "confidence": 0.85,
        }

        mock_celery_task = MagicMock()
        mock_celery_task.delay.return_value.id = "celery_hiring_456"

        with patch(
            "app.tasks.celery_tasks.voice_tasks.dispatch_voice_call_task",
            mock_celery_task,
        ):
            res = await engine.handle_hiring_radar_signal(signal_event)

        assert res.triggered is True
        assert res.trigger_type == "hiring_radar"
        assert res.task_id == "celery_hiring_456"
        assert res.phone_e164 == "+842871099999"
        mock_celery_task.delay.assert_called_once()

    async def test_low_confidence_hiring_signal_is_ignored(
        self, engine: OutboundTriggerEngine
    ):
        signal_event = {
            "workspace_id": 15,
            "phone_e164": "+842871099999",
            "signal_type": "hiring_expansion",
            "confidence": 0.60,  # Below 0.75 bar
        }

        res = await engine.handle_hiring_radar_signal(signal_event)
        assert res.triggered is False
        assert "below threshold" in res.reason

    async def test_unsupported_signal_type_is_ignored(
        self, engine: OutboundTriggerEngine
    ):
        signal_event = {
            "workspace_id": 15,
            "phone_e164": "+842871099999",
            "signal_type": "random_newsletter_click",
            "confidence": 0.99,
        }

        res = await engine.handle_hiring_radar_signal(signal_event)
        assert res.triggered is False
        assert "not an outbound trigger type" in res.reason


class TestProspectEngagementConsumer:
    """Redis stream consumer for `stream:prospect:engagement` (AI-38.2)."""

    async def test_consumer_processes_and_acks_batch(self):
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.xreadgroup = AsyncMock(
            return_value=[
                (
                    STREAM_PROSPECT_ENGAGEMENT,
                    [
                        (
                            "msg-1",
                            {
                                "workspace_id": "15",
                                "phone_e164": "+84901234567",
                                "view_duration_seconds": "50.0",
                            },
                        ),
                        (
                            "msg-2",
                            {
                                "workspace_id": "15",
                                "phone_e164": "+84901234567",
                                "view_duration_seconds": "10.0",
                            },
                        ),
                    ],
                )
            ]
        )
        mock_redis.xack = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.handle_prospect_engagement = AsyncMock()

        processed = await consume_prospect_engagement_stream(
            redis_client=mock_redis,
            engine=mock_engine,
        )

        assert processed == 2
        assert mock_engine.handle_prospect_engagement.await_count == 2
        assert mock_redis.xack.await_count == 2
        mock_redis.xack.assert_any_await(
            STREAM_PROSPECT_ENGAGEMENT, PROSPECT_ENGAGEMENT_CONSUMER_GROUP, "msg-1"
        )
        mock_redis.xack.assert_any_await(
            STREAM_PROSPECT_ENGAGEMENT, PROSPECT_ENGAGEMENT_CONSUMER_GROUP, "msg-2"
        )

    async def test_consumer_ignores_busygroup(self):
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock(
            side_effect=Exception("BUSYGROUP Consumer Group name already exists")
        )
        mock_redis.xreadgroup = AsyncMock(return_value=[])

        processed = await consume_prospect_engagement_stream(
            redis_client=mock_redis,
        )
        assert processed == 0

    async def test_consumer_error_on_one_message_does_not_ack_failure(self):
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.xreadgroup = AsyncMock(
            return_value=[
                (
                    STREAM_PROSPECT_ENGAGEMENT,
                    [
                        (
                            "msg-bad",
                            {
                                "workspace_id": "15",
                                "phone_e164": "+84901234567",
                                "view_duration_seconds": "50.0",
                            },
                        ),
                        (
                            "msg-good",
                            {
                                "workspace_id": "15",
                                "phone_e164": "+84901234567",
                                "view_duration_seconds": "50.0",
                            },
                        ),
                    ],
                )
            ]
        )
        mock_redis.xack = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.handle_prospect_engagement = AsyncMock(
            side_effect=[RuntimeError("Engine failure"), None]
        )

        processed = await consume_prospect_engagement_stream(
            redis_client=mock_redis,
            engine=mock_engine,
        )

        assert processed == 1
        assert mock_redis.xack.await_count == 1
        mock_redis.xack.assert_awaited_once_with(
            STREAM_PROSPECT_ENGAGEMENT, PROSPECT_ENGAGEMENT_CONSUMER_GROUP, "msg-good"
        )

        assert processed == 1
        assert mock_redis.xack.await_count == 1
        mock_redis.xack.assert_awaited_once_with(
            STREAM_PROSPECT_ENGAGEMENT, PROSPECT_ENGAGEMENT_CONSUMER_GROUP, "msg-good"
        )
