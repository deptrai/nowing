"""Unit tests for Telegram Stream Daemon & Alert Engine Integration (Story 22.3 / AC-3 / AD-5).

Validates Redis leader election, message stream queuing, and real-time alert rule evaluation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# AC-3: Telegram Stream Daemon Leader Election & Alert Evaluation
# ---------------------------------------------------------------------------


class TestTelegramStreamDaemonLeaderElection:
    """Validate Redis leader election for singleton daemon execution (AD-5)."""

    @pytest.mark.asyncio
    async def test_acquire_leader_lock_success(self) -> None:
        """Daemon should successfully acquire leader lock when key is unset."""
        from app.proprietary.platforms.telegram.stream_daemon import (
            TelegramStreamDaemon,
        )

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        daemon = TelegramStreamDaemon(daemon_id="daemon-node-1", redis_client=mock_redis)
        acquired = await daemon.try_acquire_leader()

        assert acquired is True
        mock_redis.set.assert_awaited_once_with(
            "telegram:daemon:leader", "daemon-node-1", nx=True, ex=30
        )

    @pytest.mark.asyncio
    async def test_standby_when_leader_lock_held_by_another_node(self) -> None:
        """Daemon must enter standby mode if another node holds the leader key."""
        from app.proprietary.platforms.telegram.stream_daemon import (
            TelegramStreamDaemon,
        )

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=None)  # Lock not acquired

        daemon = TelegramStreamDaemon(daemon_id="daemon-node-2", redis_client=mock_redis)
        acquired = await daemon.try_acquire_leader()

        assert acquired is False
        assert daemon.is_leader is False


class TestTelegramRealtimeAlertEvaluation:
    """Validate message event stream pushing and alert rule evaluation."""

    @pytest.mark.asyncio
    async def test_incoming_message_pushes_to_redis_stream(self) -> None:
        """Incoming message event must be pushed to Redis Stream 'stream:telegram:raw_events'."""
        from app.proprietary.platforms.telegram.stream_daemon import (
            TelegramStreamDaemon,
        )

        mock_redis = AsyncMock()
        daemon = TelegramStreamDaemon(daemon_id="daemon-node-1", redis_client=mock_redis)

        event_payload = {
            "channel_id": 999,
            "channel_username": "bds_hanoi_chinhchu",
            "message_id": 4567,
            "message_text": "Bán gấp nhà Cầu Giấy 12.5 tỷ, liên hệ 0912.345.678",
            "date": "2026-08-15T14:30:00Z",
        }

        await daemon.handle_incoming_message(event_payload)

        mock_redis.xadd.assert_awaited_once()
        call_args = mock_redis.xadd.await_args
        assert call_args[0][0] == "stream:telegram:raw_events"

    @pytest.mark.asyncio
    async def test_stream_event_evaluates_alert_rules(self) -> None:
        """Processing a stream event must invoke evaluate_alert_rules with extracted entities."""
        from app.proprietary.platforms.telegram.stream_daemon import (
            process_telegram_stream_event,
        )

        sample_event = {
            "channel_username": "bds_hanoi_chinhchu",
            "message_text": "Bán nhà Cầu Giấy 12.5 tỷ LH 0912345678",
            "entities": {
                "phones": ["0912345678"],
                "prices": [{"amount_vnd": 12_500_000_000, "unit": "tỷ"}],
                "locations": ["Cầu Giấy, Hà Nội"],
            },
        }

        with patch("app.alerts.engine.notify.evaluate_alert_rules", new_callable=AsyncMock) as mock_eval:
            await process_telegram_stream_event(sample_event)
            mock_eval.assert_awaited_once()
