"""Integration Tests for Story 24.1: Sequence Scheduler & Execution Engine.

Tests cover:
- AC-3: Celery Beat evaluate_pending_enrollments queue dispatch (only due scheduled enrollments)
- AC-6: Step execution transactional commit (SequenceEvent + SequenceEnrollment + BillingEvent)
- AC-7: Alert-Driven Sequence Enrollment (AlertRule trigger -> SequenceRun + SequenceEnrollment)
- AC-8: Sequence Analytics calculation (aggregate counts and micros spend)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.integration

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None, rowcount: int = 1) -> None:
        self._value = value
        self._rows = rows if rows is not None else ([value] if value is not None else [])
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
    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if not getattr(obj, "id", None):
                obj.id = uuid4()

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._scalar, self._rows)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _obj: Any) -> None:
        pass

    async def get(self, model: Any, ident: Any) -> Any:
        return self._scalar


class TestSequenceSchedulerIntegration:
    """AC-3 & AC-7: Celery Beat sequence scheduler and alert-driven enrollment."""

    async def test_evaluate_pending_enrollments_dispatches_due_tasks_only(self) -> None:
        """Only enrollments with status='scheduled' and scheduled_at <= now() are dispatched."""
        from app.services.sequencer_service import SequencerService

        session = MagicMock()
        sequencer = SequencerService()

        now = datetime.now(VN_TZ)
        due_enrollment_id = uuid4()

        # Mock query return
        due_enrollment = MagicMock(id=due_enrollment_id, workspace_id=1, status="scheduled", scheduled_at=now - timedelta(minutes=5))

        with (
            patch.object(sequencer, "get_due_enrollments", return_value=[due_enrollment]),
            patch("app.automations.tasks.sequence_tasks.execute_sequence_step.delay") as mock_delay,
        ):
            dispatched_count = await sequencer.evaluate_pending_enrollments(session=session)

            assert dispatched_count == 1
            mock_delay.assert_called_once_with(
                enrollment_id=str(due_enrollment_id),
                workspace_id=1,
            )

    async def test_alert_rule_trigger_creates_sequence_run_and_enrollment(self) -> None:
        """AC-7: When AlertRule matches, create SequenceRun with triggering_alert_rule_id and SequenceEnrollment."""
        from app.services.sequencer_service import SequencerService

        session = _FakeSession()
        sequencer = SequencerService()
        alert_rule_id = uuid4()
        sequence_id = uuid4()
        lead_id = uuid4()

        lead = MagicMock(
            id=lead_id,
            consent_status="opted_in",
            legal_basis="legitimate_interest",
            client_id="default",
        )

        result = await sequencer.enroll_lead(
            session=session,
            workspace_id=1,
            sequence_id=sequence_id,
            lead=lead,
            triggering_alert_rule_id=alert_rule_id,
        )

        assert isinstance(result, tuple)
        run, enrollment = result
        assert run.triggering_alert_rule_id == alert_rule_id
        assert run.sequence_id == sequence_id
        assert enrollment.sequence_run_id == run.id
        assert enrollment.status == "scheduled"
        assert enrollment.current_step == 1


class TestSequenceExecutionIntegration:
    """AC-6 & AC-8: Step execution transaction boundary & Analytics aggregation."""

    async def test_execute_email_step_atomic_commit_with_billing_event(self) -> None:
        """AC-6: SequenceEvent, SequenceEnrollment update and BillingEvent commit atomically."""
        from app.services.sequencer_service import SequencerService

        enrollment_id = uuid4()
        sequence_id = uuid4()
        workspace_id = 1

        enrollment = MagicMock(
            id=enrollment_id,
            workspace_id=workspace_id,
            client_id="default",
            sequence_id=sequence_id,
            lead_id=uuid4(),
            current_step=1,
            status="scheduled",
            version=0,
        )
        sequence = MagicMock(
            id=sequence_id,
            workspace_id=workspace_id,
            status="active",
            created_by_user_id=uuid4(),
        )
        step = MagicMock(
            id=uuid4(),
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            step_order=1,
            step_type="send_email",
            channel="email",
            template={"subject": "Test", "body": "Hello"},
            wait_duration_seconds=0,
            is_enabled=True,
        )
        lead = MagicMock(
            id=enrollment.lead_id,
            workspace_id=workspace_id,
            consent_status="opted_in",
            legal_basis="legitimate_interest",
            custom_fields={},
        )
        contact = MagicMock(
            consent=True,
            is_valid=True,
            email="recipient@example.com",
            confidence=0.9,
        )

        class MultiQuerySession(_FakeSession):
            async def execute(self, stmt: Any) -> _FakeResult:
                s = str(stmt).lower().strip()
                if s.startswith("update") or "update sequence_enrollments set" in s:
                    return _FakeResult(rowcount=1)
                if "step_order >" in s or "step_order>" in s:
                    return _FakeResult(value=None, rows=[])
                if "from sequence_steps" in s:
                    return _FakeResult(value=step, rows=[step])
                if "from sequence_enrollments" in s:
                    return _FakeResult(value=enrollment, rows=[enrollment])
                return _FakeResult(value=enrollment, rows=[enrollment])

            async def get(self, model: Any, ident: Any) -> Any:
                name = getattr(model, "__name__", str(model))
                if "Sequence" in name and "Step" not in name and "Enrollment" not in name:
                    return sequence
                if "Lead" in name:
                    return lead
                return MagicMock(id=1, user_id=uuid4())

        session = MultiQuerySession()
        sequencer = SequencerService()

        fake_redis = MagicMock()
        fake_lock = AsyncMock()
        fake_redis.lock.return_value = fake_lock
        fake_lock.__aenter__.return_value = fake_lock

        with (
            patch("app.services.sequencer_service.get_redis_client", new_callable=AsyncMock, return_value=fake_redis),
            patch.object(sequencer, "_resolve_verified_contact", new_callable=AsyncMock, return_value=contact),
            patch("app.services.sequencer_service.DncComplianceService.is_blocked", new_callable=AsyncMock, return_value=MagicMock(is_blocked=False)),
            patch("app.services.wallet_credit.check_balance", new_callable=AsyncMock),
            patch.object(sequencer, "_send_email_async", new_callable=AsyncMock, return_value="msg_12345"),
            patch.object(sequencer.billing_service, "record_sequence_send", new_callable=AsyncMock) as mock_record_send,
        ):
            event = await sequencer.execute_enrollment_step(
                session=session,
                enrollment_id=enrollment_id,
                workspace_id=workspace_id,
            )

            assert event is not None
            assert event.event_type == "sent"
            assert event.channel == "email"
            mock_record_send.assert_awaited_once()

    async def test_get_sequence_analytics_aggregates_metrics_correctly(self) -> None:
        """AC-8: Analytics returns aggregated counts and cost for given sequence_id."""
        from app.services.sequencer_service import SequencerService

        fake_enr_res = (10, 4, 3, 1, 0)
        fake_ev_res = (8, 4000)

        class AnalyticsSession(_FakeSession):
            def __init__(self) -> None:
                super().__init__()
                self._calls = 0

            async def execute(self, _stmt: Any) -> _FakeResult:
                self._calls += 1
                if self._calls == 1:
                    return _FakeResult(value=fake_enr_res)
                return _FakeResult(value=fake_ev_res)

        session = AnalyticsSession()
        sequencer = SequencerService()
        sequence_id = uuid4()

        analytics = await sequencer.get_sequence_analytics(
            session=session,
            workspace_id=1,
            sequence_id=sequence_id,
        )

        assert analytics.total_enrolled == 10
        assert analytics.active_scheduled == 4
        assert analytics.responded_count == 3
        assert analytics.unsubscribed_count == 1
        assert analytics.delivered_count == 8
        assert analytics.total_cost_micros == 4000
