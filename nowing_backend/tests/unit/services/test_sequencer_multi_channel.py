"""Unit tests for Story 24.7: Multi-Channel Drip Outreach Campaign Engine (Sequencer Extension).

Tests verify:
- AD-41: Channel feature-flag gate (DeferredChannelError).
- INV-24.1: Quiet hours (08:00 - 21:30 VN Time) & jitter calculation.
- INV-24.2: Consent & DNC Pre-check fail-closed.
- AD-42/AD-48: BillingEvent matrix (zns_send, telegram_send, email_send).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch
import zoneinfo

import pytest

from app.services.sequencer_service import (
    DeferredChannelError,
    SequencerService,
)


@pytest.mark.unit
class TestSequencerMultiChannelUnit:
    """ATDD Unit Test Scaffolds for Story 24.7."""

    def test_channel_feature_flag_validation(self):
        """AC-2: Test channel validation against SEQUENCER_OUTBOUND_CHANNELS config."""
        service = SequencerService()

        # Case 1: Default config is only "email"
        with patch("app.config.config.SEQUENCER_OUTBOUND_CHANNELS", "email"):
            assert service.validate_step_channel("email") is True
            with pytest.raises(DeferredChannelError):
                service.validate_step_channel("zalo")
            with pytest.raises(DeferredChannelError):
                service.validate_step_channel("telegram")

        # Case 2: Config enabled for all channels
        with patch("app.config.config.SEQUENCER_OUTBOUND_CHANNELS", "email,zalo,telegram"):
            assert service.validate_step_channel("email") is True
            assert service.validate_step_channel("zalo") is True
            assert service.validate_step_channel("telegram") is True

    def test_quiet_hours_and_jitter_scheduling(self):
        """AC-3: Test calculate_step_eta respects 08:00 - 21:30 VN Time."""
        service = SequencerService()
        vn_tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

        # Case 1: Within quiet hours (e.g. 22:30 night)
        night_time = datetime(2026, 8, 22, 22, 30, 0, tzinfo=vn_tz)
        scheduled_eta = service.calculate_step_eta(target_dt=night_time, delay_seconds=0)

        # Must be moved to next morning 08:05 + jitter (up to 30 min)
        eta_vn = scheduled_eta.astimezone(vn_tz)
        assert eta_vn.day == 23
        assert eta_vn.hour == 8
        assert eta_vn.minute >= 5

        # Case 2: Within active hours (e.g. 10:00 AM)
        active_time = datetime(2026, 8, 22, 10, 0, 0, tzinfo=vn_tz)
        scheduled_eta_active = service.calculate_step_eta(target_dt=active_time, delay_seconds=3600)
        eta_active_vn = scheduled_eta_active.astimezone(vn_tz)
        assert eta_active_vn.day == 22
        assert eta_active_vn.hour == 11

    @pytest.mark.asyncio
    async def test_consent_and_dnc_precheck_multi_channel(self):
        """AC-4: Test DNC and Consent fail-closed checks before step execution."""
        service = SequencerService()

        # Mock DNC service blocking
        with patch("app.services.dnc_compliance_service.DncComplianceService.is_blocked", new_callable=AsyncMock) as mock_dnc:
            mock_dnc.return_value = True
            is_allowed = await service.check_outbound_compliance(
                workspace_id=1,
                phone="0909123456",
                channel="zalo",
                consent_status="opted_in",
                legal_basis="legitimate_interest",
            )
            assert is_allowed is False

            # Case: Not blocked and valid consent
            mock_dnc.return_value = False
            is_allowed_valid = await service.check_outbound_compliance(
                workspace_id=1,
                phone="0909123456",
                channel="zalo",
                consent_status="opted_in",
                legal_basis="legitimate_interest",
            )
            assert is_allowed_valid is True

    def test_billing_event_emission_matrix(self):
        """AC-7: Test billing event mapping for each channel."""
        service = SequencerService()

        email_event = service.get_billing_event_for_step(channel="email", event_type="sent")
        assert email_event["event_type"] == "email_send"
        assert email_event["event_entity_type"] == "sequence_event"

        zalo_event = service.get_billing_event_for_step(channel="zalo", event_type="sent")
        assert zalo_event["event_type"] == "zns_send"
        assert zalo_event["event_entity_type"] == "sequence_event"

        tg_event = service.get_billing_event_for_step(channel="telegram", event_type="sent")
        assert tg_event["event_type"] == "telegram_send"
        assert tg_event["event_entity_type"] == "sequence_event"
