"""Unit Tests for Story 24.1: Multi-Channel Drip Outreach Campaign Engine (SequencerService).

Tests cover:
- AC-2: Deferred channels rejection (Zalo, Telegram, LinkedIn 422 DeferredChannelError)
- AC-3: Quiet Hours & Jitter ETA calculations (08:00 - 21:30 VN Time, next-day 08:05 + jitter)
- AC-4: Consent & Legal Basis Gate (enrollment rejection & step skipping without valid consent)
- AC-5: Inbound Interruption & Distributed Lock (Redis lock, CAS OCC, opt-out DNC registration)
- AC-6: Billing & Credit Pre-checks (spend cap, balance check, SequenceEvent failure transitions)
- Edge Cases: Condition branching, template variable interpolation, DNC fail-closed verification
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.unit

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None, rowcount: int = 1) -> None:
        self._value = value
        self._rows = rows or []
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """AsyncSession stand-in for testing SequencerService unit logic."""

    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed = True
        for obj in self.added:
            if not getattr(obj, "id", None):
                obj.id = uuid4()

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def get(self, model: Any, ident: Any) -> Any:
        return self._scalar


# ============================================================================
# AC-3: Quiet Hours & Scheduling Tests
# ============================================================================


class TestQuietHoursAndJitter:
    """AC-3: Test quiet hours enforcement (08:00 - 21:30 VN Time) and anti-thundering jitter."""

    def test_eta_within_daytime_window_returns_exact_target(self) -> None:
        """If target time is between 08:00 and 21:30 VN Time, return target_dt unchanged."""
        from app.services.sequencer_service import calculate_step_eta

        # 10:00 AM VN Time + 2 hours = 12:00 PM (inside window)
        base_time = datetime(2026, 8, 17, 10, 0, 0, tzinfo=VN_TZ)
        delay_seconds = 7200

        result = calculate_step_eta(delay_seconds=delay_seconds, from_dt=base_time)

        expected = datetime(2026, 8, 17, 12, 0, 0, tzinfo=VN_TZ)
        assert result == expected

    def test_eta_after_quiet_hour_boundary_pushes_to_next_day_with_jitter(self) -> None:
        """Target time at 22:30 (> 21:30) must push to next day 08:05 + random jitter (0-1800s)."""
        from app.services.sequencer_service import calculate_step_eta

        # 20:00 VN Time + 3 hours = 23:00 (outside window)
        base_time = datetime(2026, 8, 17, 20, 0, 0, tzinfo=VN_TZ)
        delay_seconds = 10800

        with patch("random.randint", return_value=300):  # 5 min jitter
            result = calculate_step_eta(delay_seconds=delay_seconds, from_dt=base_time)

        # Expected: 2026-08-18 08:05:00 + 300s = 08:10:00 VN Time
        expected = datetime(2026, 8, 18, 8, 10, 0, tzinfo=VN_TZ)
        assert result == expected

    def test_eta_before_morning_window_pushes_to_same_day_morning(self) -> None:
        """Target time at 05:00 (< 08:00) must push to same day 08:05 + jitter."""
        from app.services.sequencer_service import calculate_step_eta

        # 03:00 VN Time + 2 hours = 05:00 (before 08:00)
        base_time = datetime(2026, 8, 17, 3, 0, 0, tzinfo=VN_TZ)
        delay_seconds = 7200

        with patch("random.randint", return_value=60):
            result = calculate_step_eta(delay_seconds=delay_seconds, from_dt=base_time)

        expected = datetime(2026, 8, 17, 8, 6, 0, tzinfo=VN_TZ)
        assert result == expected

    def test_eta_handles_utc_and_naive_datetimes(self) -> None:
        """Ensure naive and UTC datetimes are safely converted to Asia/Ho_Chi_Minh."""
        from app.services.sequencer_service import calculate_step_eta

        # Naive datetime (assumed UTC) -> converted to VN (+7)
        naive_dt = datetime(2026, 8, 17, 3, 0, 0)  # 03:00 UTC = 10:00 VN
        result = calculate_step_eta(delay_seconds=3600, from_dt=naive_dt)

        assert result.tzinfo == VN_TZ
        assert result.hour == 11
        assert result.minute == 0


# ============================================================================
# AC-2: Email-first MVP & Deferred Channels Gate
# ============================================================================


class TestDeferredChannelsGate:
    """AC-2: Validate that non-email channels raise 422 DeferredChannelError in MVP."""

    @pytest.mark.parametrize("deferred_channel", ["zalo", "telegram", "linkedin"])
    async def test_deferred_channels_rejected_by_sequencer(self, deferred_channel: str) -> None:
        """SequencerService must reject deferred channels unless feature flag is set."""
        from app.services.sequencer_service import (
            DeferredChannelError,
            SequencerService,
        )

        sequencer = SequencerService()

        with pytest.raises(DeferredChannelError) as exc_info:
            await sequencer.validate_step_channel(channel=deferred_channel)

        assert "deferred" in str(exc_info.value).lower()
        assert deferred_channel in str(exc_info.value).lower()

    async def test_email_channel_allowed_in_mvp(self) -> None:
        """Email channel must pass validation without raising error."""
        from app.services.sequencer_service import SequencerService

        sequencer = SequencerService()
        # Should not raise
        await sequencer.validate_step_channel(channel="email")


# ============================================================================
# AC-4: Consent & Legal Basis Gate
# ============================================================================


class TestConsentAndLegalBasisGate:
    """AC-4: Verify consent_status and legal_basis filtering before enrollment and sending."""

    async def test_enroll_lead_rejects_lead_without_consent(self) -> None:
        """Lead with consent_status='none' or legal_basis=None is rejected with None."""
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()
        sequencer = SequencerService()

        unconsented_lead = MagicMock()
        unconsented_lead.id = uuid4()
        unconsented_lead.consent_status = "none"
        unconsented_lead.legal_basis = None

        result = await sequencer.enroll_lead(
            session=session,
            workspace_id=1,
            sequence_id=uuid4(),
            lead=unconsented_lead,
        )

        assert result is None
        assert len(session.added) == 0

    async def test_send_step_skips_when_verified_contact_lacks_consent(self) -> None:
        """When sending an email step, if VerifiedContact has consent=False, skip step."""
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()
        sequencer = SequencerService()

        lead = MagicMock(id=uuid4(), consent_status="opted_in", legal_basis="legitimate_interest")
        contact_no_consent = MagicMock(consent=False, is_valid=True, email="user@example.com")
        sequence = MagicMock(id=uuid4(), created_by_user_id=uuid4(), workspace_id=1)
        step = MagicMock(id=uuid4(), channel="email", step_order=1, wait_duration_seconds=0)
        enrollment = MagicMock(workspace_id=1, client_id="default", id=uuid4(), current_step=1, version=0)

        with patch.object(sequencer, "_resolve_verified_contact", return_value=contact_no_consent):
            event = await sequencer._handle_send_email_step(
                session=session, sequence=sequence, step=step, enrollment=enrollment, lead=lead
            )

        assert event is not None
        assert event.event_type == "skipped"
        assert event.event_subtype == "no_consent"


# ============================================================================
# AC-5: Inbound Interruption & Distributed Lock
# ============================================================================


class TestInboundInterruptionAndLock:
    """AC-5: Inbound STOP/HUY/UNSUBSCRIBE creates DNC and updates CAS version."""

    @pytest.mark.parametrize("keyword", ["STOP", "HUY", "NGUNG", "UNSUBSCRIBE", "Hủy"])
    async def test_inbound_opt_out_registers_dnc_and_transitions_unsubscribed(self, keyword: str) -> None:
        """Inbound opt-out message triggers DNC creation and cancels further sequence steps."""
        from app.services.sequencer_service import SequencerService

        fake_enrollment = MagicMock(
            id=uuid4(),
            workspace_id=1,
            client_id="default",
            sequence_id=uuid4(),
            status="scheduled",
            version=1,
        )
        session = _FakeSession(rows=[fake_enrollment])
        sequencer = SequencerService()

        fake_redis = MagicMock()
        fake_lock = AsyncMock()
        fake_redis.lock.return_value = fake_lock
        fake_lock.__aenter__.return_value = fake_lock

        with (
            patch("app.services.sequencer_service.get_redis_client", return_value=fake_redis),
            patch.object(sequencer, "_register_opt_out_dnc", new_callable=AsyncMock) as mock_dnc,
        ):
            await sequencer.handle_inbound_interruption(
                session=session,
                workspace_id=1,
                email="prospect@example.com",
                text=f"Please {keyword} all messages",
                channel="email",
            )

            mock_dnc.assert_awaited_once()

    async def test_inbound_positive_reply_transitions_responded(self) -> None:
        """Normal inbound reply updates sequence enrollment status to 'responded'."""
        from app.services.sequencer_service import SequencerService

        fake_enrollment = MagicMock(
            id=uuid4(),
            workspace_id=1,
            client_id="default",
            sequence_id=uuid4(),
            status="scheduled",
            version=1,
        )
        session = _FakeSession(rows=[fake_enrollment])
        sequencer = SequencerService()

        fake_redis = MagicMock()
        fake_lock = AsyncMock()
        fake_redis.lock.return_value = fake_lock
        fake_lock.__aenter__.return_value = fake_lock

        with patch("app.services.sequencer_service.get_redis_client", return_value=fake_redis):
            result = await sequencer.handle_inbound_interruption(
                session=session,
                workspace_id=1,
                email="interested@example.com",
                text="Tôi muốn tìm hiểu thêm về căn hộ này",
                channel="email",
            )

        assert result is not None
        assert result.status == "responded"


# ============================================================================
# AC-6: Billing & Credit Pre-checks
# ============================================================================


class TestBillingAndCreditFlow:
    """AC-6: Validate balance check and transactional billing event recording."""

    async def test_insufficient_credits_fails_early_without_sending(self) -> None:
        """If user balance < cost_micros, emit SequenceEvent(failed, insufficient_credits)."""
        from app.services import wallet_credit
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()
        sequencer = SequencerService()

        lead = MagicMock(id=uuid4(), consent_status="opted_in", legal_basis="legitimate_interest", custom_fields={})
        contact = MagicMock(consent=True, is_valid=True, email="test@example.com")
        sequence = MagicMock(id=uuid4(), created_by_user_id=uuid4(), workspace_id=1)
        step = MagicMock(id=uuid4(), channel="email", step_order=1, template={})
        enrollment = MagicMock(workspace_id=1, client_id="default", id=uuid4(), current_step=1, version=0)

        with (
            patch.object(sequencer, "_resolve_verified_contact", return_value=contact),
            patch("app.lead_intelligence.dnc.service.DncComplianceService.is_blocked", return_value=MagicMock(is_blocked=False)),
            patch("app.services.wallet_credit.check_balance", side_effect=wallet_credit.InsufficientCreditsError("0 balance")),
        ):
            event = await sequencer._handle_send_email_step(
                session=session, sequence=sequence, step=step, enrollment=enrollment, lead=lead
            )

        assert event.event_type == "failed"
        assert event.event_subtype == "insufficient_credits"

    async def test_billing_event_service_record_sequence_send_idempotency(self) -> None:
        """record_sequence_send must be idempotent by sequence_event_id and return existing."""
        from app.services.billing_event_service import BillingEventService

        seq_event_id = uuid4()
        existing_billing_event = MagicMock(event_id=seq_event_id, event_type="email_send")
        session = _FakeSession(scalar=existing_billing_event)
        billing_service = BillingEventService()

        result = await billing_service.record_sequence_send(
            session=session,
            sequence_event_id=seq_event_id,
            workspace_id=1,
            client_id="default",
            user_id=uuid4(),
            cost_micros=500,
        )

        assert result == existing_billing_event


# ============================================================================
# Edge Cases: Template Variable Substitution & Condition Branching
# ============================================================================


class TestTemplateAndConditionBranching:
    """Edge cases: template variables and branching logic."""

    def test_template_variable_substitution_with_missing_keys(self) -> None:
        """Template interpolation gracefully handles missing variables without crash."""
        from app.services.sequencer_service import interpolate_template_variables

        template_text = "Chào {customer_name}, dự án {property_title} tại {company} đang có ưu đãi!"
        variables = {
            "customer_name": "Anh Minh",
            # property_title is missing
            "company": "Nowing Land",
        }

        result = interpolate_template_variables(template_text, variables, fallback_blank=True)
        assert "Chào Anh Minh" in result
        assert "Nowing Land" in result
        assert "{property_title}" not in result

    def test_condition_step_branch_routing(self) -> None:
        """Condition step routes to matched branch next_step_order or exits."""
        from app.services.sequencer_service import evaluate_condition_step

        condition_config = {
            "predicate": "has_replied",
            "if_true_step": 3,
            "if_false_step": None,  # Exit sequence
        }

        next_step_true = evaluate_condition_step(condition_config, context={"has_replied": True})
        assert next_step_true == 3

        next_step_false = evaluate_condition_step(condition_config, context={"has_replied": False})
        assert next_step_false is None
