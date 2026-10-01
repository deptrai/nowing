"""Unit tests for Sequencer voice dispatch (Story 38.7 Action Executor)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


def _make_mixin():
    from app.services.sequencer.dispatch import SequencerDispatchMixin

    mixin = SequencerDispatchMixin.__new__(SequencerDispatchMixin)
    mixin.encryption = MagicMock()
    mixin.encryption.is_encrypted = MagicMock(return_value=False)
    return mixin


def _make_contact(phone: str | None = "+84901234567"):
    contact = MagicMock()
    contact.phone = phone
    contact.email = "ceo@corp.vn"
    contact.external_chat_ids = {}
    return contact


def _make_enrollment():
    enrollment = MagicMock()
    enrollment.workspace_id = 15
    return enrollment


def _make_lead():
    lead = MagicMock()
    lead.id = uuid4()
    return lead


class TestAllowedChannels:
    """Voice channel visibility in Sequencer constants."""

    def test_voice_included_when_flag_enabled(self, monkeypatch):
        from app.services.sequencer import constants

        monkeypatch.setattr(
            "app.config.voice.SEQUENCER_VOICE_ENABLED", True, raising=False
        )
        channels = constants.get_allowed_outbound_channels()
        assert "voice" in channels
        assert "email" in channels

    def test_voice_excluded_when_flag_disabled(self, monkeypatch):
        from app.services.sequencer import constants

        monkeypatch.setattr("app.config.voice.SEQUENCER_VOICE_ENABLED", False)
        channels = constants.get_allowed_outbound_channels()
        assert "voice" not in channels


class TestVoiceDispatchRouting:
    """_dispatch_single_channel routes 'voice' channel to _send_voice_dispatch."""

    async def test_voice_dispatch_calls_send_voice_dispatch(self, monkeypatch):
        import app.config.voice as voice_cfg
        from app.services.sequencer import dispatch as dispatch_mod

        monkeypatch.setattr(voice_cfg, "SEQUENCER_VOICE_ENABLED", True)
        monkeypatch.setattr(
            dispatch_mod, "SEQUENCER_VOICE_ENABLED", True, raising=False
        )

        mixin = _make_mixin()
        mixin._send_voice_dispatch = AsyncMock(return_value="call_abc123")

        step = MagicMock()
        step.channel = "voice"
        enrollment = _make_enrollment()
        lead = _make_lead()
        contact = _make_contact()

        msg_id, used_channel = await mixin._dispatch_single_channel(
            session=MagicMock(),
            sequence=MagicMock(),
            step=step,
            enrollment=enrollment,
            lead=lead,
            contact=contact,
            channel="voice",
            template_data={},
            context_vars={},
            attributed_user_id=None,
            cost_micros=0,
        )

        assert used_channel == "voice"
        assert msg_id == "call_abc123"
        mixin._send_voice_dispatch.assert_awaited_once()

    async def test_voice_channel_disabled_raises(self, monkeypatch):
        import app.config.voice as voice_cfg
        from app.services.sequencer import dispatch as dispatch_mod

        monkeypatch.setattr(voice_cfg, "SEQUENCER_VOICE_ENABLED", False)
        monkeypatch.setattr(
            dispatch_mod, "SEQUENCER_VOICE_ENABLED", False, raising=False
        )

        mixin = _make_mixin()

        step = MagicMock()
        step.channel = "voice"
        enrollment = _make_enrollment()
        lead = _make_lead()
        contact = _make_contact()

        with pytest.raises(ValueError, match="voice_channel_disabled"):
            await mixin._dispatch_single_channel(
                session=MagicMock(),
                sequence=MagicMock(),
                step=step,
                enrollment=enrollment,
                lead=lead,
                contact=contact,
                channel="voice",
                template_data={},
                context_vars={},
                attributed_user_id=None,
                cost_micros=0,
            )

    async def test_missing_phone_raises(self, monkeypatch):
        import app.config.voice as voice_cfg
        from app.services.sequencer import dispatch as dispatch_mod

        monkeypatch.setattr(voice_cfg, "SEQUENCER_VOICE_ENABLED", True)
        monkeypatch.setattr(
            dispatch_mod, "SEQUENCER_VOICE_ENABLED", True, raising=False
        )

        mixin = _make_mixin()

        step = MagicMock()
        step.channel = "voice"
        enrollment = _make_enrollment()
        lead = _make_lead()

        with pytest.raises(ValueError, match="missing_phone"):
            await mixin._dispatch_single_channel(
                session=MagicMock(),
                sequence=MagicMock(),
                step=step,
                enrollment=enrollment,
                lead=lead,
                contact=_make_contact(None),
                channel="voice",
                template_data={},
                context_vars={},
                attributed_user_id=None,
                cost_micros=0,
            )


class TestSendVoiceDispatch:
    """_send_voice_dispatch: compliance gate + trunk resolution + LiveKit dispatch."""

    async def test_compliance_rejection_raises_value_error(self, monkeypatch):
        from app.services.voice.compliance_gate import ComplianceVerdict

        mixin = _make_mixin()

        async def _rejected(self, session, workspace_id, raw_phone, **kwargs):
            return MagicMock(
                allowed=False,
                verdict=ComplianceVerdict.DNC_BLOCKED,
                phone_e164="+84901234567",
                reserved_micros=0,
            )

        monkeypatch.setattr(
            "app.services.voice.compliance_gate.TelephonyComplianceGate.evaluate_preflight",
            _rejected,
        )

        with pytest.raises(ValueError, match="compliance_rejected_dnc_blocked"):
            await mixin._send_voice_dispatch(
                MagicMock(),
                workspace_id=15,
                user_id=None,
                phone_e164="+84901234567",
            )

    async def test_infrastructure_failure_releases_locks(self, monkeypatch):
        """LiveKit failure after gate approval must release lock + deposit."""
        from app.services.voice.compliance_gate import (
            ComplianceCheckResult,
        )

        mixin = _make_mixin()
        released: list[str] = []

        async def _approved(self, session, workspace_id, raw_phone, **kwargs):
            return ComplianceCheckResult.allow(
                phone_e164="+84901234567", lock_key="k", reserved_micros=7_500_000
            )

        async def _release_lock(self, workspace_id, phone_e164):
            released.append("lock")

        async def _release_deposit(session, user_id, amount_micros):
            released.append("deposit")

        async def _resolve_trunk(self, session, workspace_id):
            return MagicMock(trunk_id="trunk_1", sip_password="x")

        class _FailingTelephony:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def dispatch_call(self, **kwargs):
                raise RuntimeError("SIP 503 unavailable")

        monkeypatch.setattr(
            "app.services.voice.compliance_gate.TelephonyComplianceGate.evaluate_preflight",
            _approved,
        )
        monkeypatch.setattr(
            "app.services.voice.compliance_gate.TelephonyComplianceGate.release_frequency_lock",
            _release_lock,
        )
        monkeypatch.setattr(
            "app.services.voice.compliance_gate.TelephonyComplianceGate.release_deposit",
            staticmethod(_release_deposit),
        )
        monkeypatch.setattr(
            "app.services.voice.sip_manager.SipTrunkManager.resolve_workspace_trunk",
            _resolve_trunk,
        )
        monkeypatch.setattr(
            "app.services.voice.telephony_client.LiveKitTelephonyClient",
            _FailingTelephony,
        )

        with pytest.raises(RuntimeError):
            await mixin._send_voice_dispatch(
                MagicMock(),
                workspace_id=15,
                user_id=uuid4(),
                phone_e164="+84901234567",
            )

        assert "lock" in released
        assert "deposit" in released

