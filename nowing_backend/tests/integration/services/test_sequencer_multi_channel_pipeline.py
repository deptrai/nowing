"""Integration tests for Story 24.7: Multi-Channel Drip Outreach Campaign Engine (Fallback & Inbound Interruption).

Tests verify:
- AC-5: Multi-channel send with fallback (Zalo ➔ Telegram ➔ Email).
- AC-6: Inbound interruption & distributed Redis lock (INV-24.7).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.sequencer_service import SequencerService


@pytest.mark.integration
class TestSequencerMultiChannelPipelineIntegration:
    """ATDD Integration Test Scaffolds for Story 24.7."""

    @pytest.mark.asyncio
    async def test_multi_channel_send_with_fallback_pipeline(self):
        """AC-5: Test step fallback from Zalo to Telegram when Zalo fails."""
        service = SequencerService()

        # Mock ZNS failing permanently
        mock_zns = AsyncMock()
        mock_zns.send_zns_template.side_effect = Exception("phone_not_registered")

        # Mock Telegram succeeding
        mock_telegram = AsyncMock()
        mock_telegram.send_message.return_value = {"message_id": 9999, "status": "sent"}

        with (
            patch("app.config.config.SEQUENCER_OUTBOUND_CHANNELS", "email,zalo,telegram"),
            patch.object(service, "_send_zns_step", mock_zns.send_zns_template),
            patch.object(service, "_send_telegram_step", mock_telegram.send_message),
        ):
            result = await service.execute_step_with_fallback(
                workspace_id=1,
                lead_id="lead_123",
                primary_channel="zalo",
                fallback_channels=["telegram", "email"],
                step_data={"text": "Chào bạn, mình gửi thông tin dự án nhé."},
            )

            assert result["status"] == "sent"
            assert result["successful_channel"] == "telegram"
            assert result["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_inbound_interruption_distributed_lock(self):
        """AC-6: Test inbound interruption locks enrollment and pauses sequence."""
        service = SequencerService()

        redis_mock = AsyncMock()
        redis_mock.set.return_value = True  # lock acquired

        with patch.object(service, "_get_redis", return_value=redis_mock):
            interrupted = await service.handle_inbound_interruption(
                workspace_id=1,
                enrollment_id=101,
                reason="prospect_replied_on_zalo",
            )
            assert interrupted is True
            # Verify lock key format
            lock_key = "sequence:lock:enrollment:1:101"
            assert any(call.args and lock_key in call.args[0] for call in redis_mock.set.call_args_list)
