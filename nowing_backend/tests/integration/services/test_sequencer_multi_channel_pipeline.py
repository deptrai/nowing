"""Integration tests for Story 24.7: Multi-Channel Drip Outreach Campaign Engine (Fallback & Inbound Interruption).

Tests verify:
- AC-5: Multi-channel send with fallback (Zalo ➔ Telegram ➔ Email).
- AC-6: Inbound interruption & distributed Redis lock (INV-24.7).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.sequencer_service import SequencerService


@pytest.mark.integration
class TestSequencerMultiChannelPipelineIntegration:
    """ATDD Integration Test Scaffolds for Story 24.7."""

    @pytest.mark.asyncio
    async def test_multi_channel_send_with_fallback_pipeline(self):
        """AC-5: Test step fallback from Zalo to Telegram when Zalo fails."""
        service = SequencerService()

        step = MagicMock(
            id=uuid4(),
            step_order=1,
            step_type="send_zalo",
            channel="zalo",
            fallback_channels=["telegram", "email"],
            template={
                "template_id": "ZNS_OUTREACH_APPROVED_01",
                "template_data": {"customer_name": "Alice"},
                "body": "Chào bạn",
            },
            wait_duration_seconds=0,
            condition_config={},
            is_enabled=True,
        )
        sequence = MagicMock(id=uuid4(), workspace_id=1, client_id="default")
        enrollment = MagicMock(
            id=uuid4(),
            workspace_id=1,
            client_id="default",
            lead_id=uuid4(),
            current_step=1,
            version=1,
            status="scheduled",
        )
        lead = MagicMock(
            id=enrollment.lead_id,
            workspace_id=1,
            phone="+84909123456",
            consent_status="opted_in",
            legal_basis="legitimate_interest",
        )
        contact = MagicMock(
            id=uuid4(),
            lead_id=lead.id,
            workspace_id=1,
            phone="+84909123456",
            external_chat_ids={"telegram_chat_id": "12345"},
            email="alice@example.com",
            consent=True,
            is_valid=True,
        )
        session = AsyncMock()

        with (
            patch(
                "app.config.config.SEQUENCER_OUTBOUND_CHANNELS", "email,zalo,telegram"
            ),
            patch(
                "app.config.config.AD_41_REACTIVATED", True
            ),
            patch.object(
                service, "_resolve_verified_contact", new_callable=AsyncMock, return_value=contact
            ),
            patch(
                "app.services.sequencer_service.DncComplianceService.is_blocked",
                new_callable=AsyncMock,
                return_value=MagicMock(is_blocked=False),
            ),
            patch("app.services.wallet_credit.check_balance", new_callable=AsyncMock),
            patch.object(
                service, "_send_zns_dispatch", new_callable=AsyncMock, side_effect=Exception("phone_not_registered")
            ),
            patch.object(
                service, "_send_telegram_dispatch", new_callable=AsyncMock, return_value="msg_tg_9999"
            ),
            patch.object(
                service, "_send_email_dispatch", new_callable=AsyncMock, return_value="msg_email_12345"
            ),
            patch.object(
                service.billing_service, "record_sequence_send", new_callable=AsyncMock
            ),
            patch.object(service, "_advance_to_next_step", new_callable=AsyncMock),
        ):
            event = await service._handle_send_step(
                session=session,
                sequence=sequence,
                step=step,
                enrollment=enrollment,
                lead=lead,
            )

            assert event is not None
            assert event.event_type == "sent"
            assert event.channel == "telegram"
            assert event.cost_micros == 0  # telegram cost when fallback used

    @pytest.mark.asyncio
    async def test_inbound_interruption_distributed_lock(self):
        """AC-6: Test inbound interruption locks enrollment and pauses sequence."""
        service = SequencerService()

        redis_mock = AsyncMock()
        redis_mock.set.return_value = True  # lock acquired

        with patch.object(service, "_get_redis_async", new_callable=AsyncMock, return_value=redis_mock):
            interrupted = await service.handle_inbound_interruption(
                workspace_id=1,
                enrollment_id=101,
                reason="prospect_replied_on_zalo",
            )
            assert interrupted is True
            # Verify lock key format
            lock_key = "sequence:lock:enrollment:1:101"
            assert any(
                call.args and lock_key in call.args[0]
                for call in redis_mock.set.call_args_list
            )
