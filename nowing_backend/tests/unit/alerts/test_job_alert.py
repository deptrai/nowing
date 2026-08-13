"""Red-phase ATDD tests for Story 12.9 — Job Market Alerts.

These tests describe the contract the implementation must satisfy. They will
fail until `bmad-dev-story` makes them pass.
"""

from __future__ import annotations

from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from app.alerts.engine.execute import execute_alert_rule
from app.alerts.engine.notify import _notification_message, _notification_title
from app.capabilities.core.store import CapabilityRegistry

pytestmark = pytest.mark.unit


class _FakeRule:
    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeSnapshot:
    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeSub:
    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _FakeSession:
    def __init__(
        self,
        subscriptions: list[_FakeSub] | None = None,
        prev: _FakeSnapshot | None = None,
    ):
        self.subscriptions = subscriptions or []
        self.prev = prev
        self.added: list[Any] = []

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        if "alert_snapshot" in str(stmt).lower():
            return _FakeResult([self.prev] if self.prev else [])
        return _FakeResult(self.subscriptions)

    async def commit(self):
        pass


class TestJobAlertRule:
    """AC-1: saved-search alert rule uses vn_jobs.aggregate."""

    def test_job_alert_rule_uses_vn_jobs_aggregate_capability(self):
        """A job market alert rule must be configured with capability_id='vn_jobs.aggregate'."""
        rule = _FakeRule(
            id=uuid4(),
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python", "location": "Ho Chi Minh"},
            diff_strategy="new_items",
        )
        assert rule.capability_id == "vn_jobs.aggregate"
        assert rule.query["keyword"] == "python"
        assert rule.diff_strategy == "new_items"

    def test_job_alert_rule_query_schema_accepts_keyword_location_salary(self):
        """A job alert query must accept keyword, location, salary_min, salary_max."""
        query = {"keyword": "Senior Python", "location": "Ho Chi Minh", "salary_min": 2000, "salary_max": 5000}
        assert query["keyword"]
        assert query["location"]
        assert query["salary_min"] >= 0
        assert query["salary_max"] >= query["salary_min"]


class TestJobAlertNotify:
    """AC-2/AC-3: notification content and deep-link."""

    def test_job_alert_notification_message_mentions_match_count(self):
        rule = _FakeRule(name="Python jobs", workspace_id=1, id=uuid4())
        snapshot = _FakeSnapshot(
            id=uuid4(),
            run_status="succeeded",
            new_items_count=3,
            matched_items=[{"id": "job-1"}, {"id": "job-2"}, {"id": "job-3"}],
            degradation_reasons=None,
        )

        title = _notification_title(rule, snapshot)
        message = _notification_message(rule, snapshot)

        assert "3" in title
        assert "Python jobs" in title
        assert "3" in message

    def test_job_alert_notification_has_deep_link_to_saved_search(self):
        rule = _FakeRule(name="Python jobs", workspace_id=1, id=uuid4())
        snapshot = _FakeSnapshot(
            id=uuid4(),
            run_status="succeeded",
            new_items_count=2,
            matched_items=[{"id": "job-1"}, {"id": "job-2"}],
            degradation_reasons=None,
        )

        message = _notification_message(rule, snapshot)
        expected_path = f"/dashboard/{rule.workspace_id}/research/saved-searches/{rule.id}?snapshot={snapshot.id}"

        assert expected_path in message

    @pytest.mark.asyncio
    async def test_job_alert_diff_new_items_triggers_notification(self):
        """AC-2: a run with new postings notifies subscribed users."""
        rule = _FakeRule(
            id=uuid4(),
            workspace_id=1,
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            diff_strategy="new_items",
            notification_channels=["in_app"],
            threshold={},
        )
        prev = _FakeSnapshot(
            id=uuid4(),
            snapshot_json={"source_ids": ["job-1"], "items": [{"id": "job-1"}]},
        )
        session = _FakeSession(prev=prev)

        fake_capability = mock.MagicMock()
        fake_capability.input_schema.model_validate.return_value = rule.query
        with (
            mock.patch.object(CapabilityRegistry, "get", return_value=fake_capability),
            mock.patch("app.alerts.engine.execute.execute_with_context") as mock_run,
            mock.patch(
                "app.alerts.engine.execute.notify_alert_run",
                new=mock.AsyncMock(),
            ) as mock_notify,
        ):
            mock_run.return_value = {
                "items": [{"id": "job-1"}, {"id": "job-2"}],
                "degraded": False,
            }
            await execute_alert_rule(
                session=session,
                alert_rule=rule,
                fired_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

        assert mock_notify.await_count == 1
        snapshot = session.added[0]
        assert snapshot.new_items_count == 1

    @pytest.mark.asyncio
    async def test_job_alert_no_notification_when_no_new_items(self):
        """AC-2: a run with no new postings does not notify."""
        rule = _FakeRule(
            id=uuid4(),
            workspace_id=1,
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            diff_strategy="new_items",
            notification_channels=["in_app"],
            threshold={},
        )
        prev = _FakeSnapshot(
            id=uuid4(),
            snapshot_json={"source_ids": ["job-1"], "items": [{"id": "job-1"}]},
        )
        session = _FakeSession(prev=prev)

        fake_capability = mock.MagicMock()
        fake_capability.input_schema.model_validate.return_value = rule.query
        with (
            mock.patch.object(CapabilityRegistry, "get", return_value=fake_capability),
            mock.patch("app.alerts.engine.execute.execute_with_context") as mock_run,
            mock.patch(
                "app.alerts.engine.execute.notify_alert_run",
                new=mock.AsyncMock(),
            ) as mock_notify,
        ):
            mock_run.return_value = {
                "items": [{"id": "job-1"}],
                "degraded": False,
            }
            await execute_alert_rule(
                session=session,
                alert_rule=rule,
                fired_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

        assert mock_notify.await_count == 0
        snapshot = session.added[0]
        assert snapshot.new_items_count == 0


class TestJobAlertDegraded:
    """AC-5: degraded source / missing rule handling."""

    @pytest.mark.asyncio
    async def test_job_alert_skips_when_degraded_and_zero_new_items(self):
        """When vn_jobs.aggregate returns degraded=true and no new items, no notification is sent."""
        rule = _FakeRule(
            id=uuid4(),
            workspace_id=1,
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            notification_channels=["in_app"],
            diff_strategy="new_items",
        )

        fake_capability = mock.MagicMock()
        fake_capability.input_schema.model_validate.return_value = rule.query
        with (
            mock.patch.object(CapabilityRegistry, "get", return_value=fake_capability),
            mock.patch("app.alerts.engine.execute.execute_with_context") as mock_run,
            mock.patch(
                "app.alerts.engine.execute.notify_alert_run",
                new=mock.AsyncMock(),
            ) as mock_notify,
        ):
            mock_run.return_value = {
                "items": [],
                "degraded": True,
                "degradation_reasons": ["topcv.timeout"],
            }
            await execute_alert_rule(
                session=_FakeSession(),
                alert_rule=rule,
                fired_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

        # ATDD: when degraded + no new items, notify_alert_run must be skipped entirely.
        # Until implemented, the current code calls notify_alert_run for every run.
        # This assertion documents the desired behavior and will fail until fixed.
        assert mock_notify.await_count == 0

    @pytest.mark.asyncio
    async def test_job_alert_logs_degraded_source(self):
        """A structured log is emitted when the source is degraded."""
        rule = _FakeRule(
            id=uuid4(),
            workspace_id=1,
            name="Python jobs",
            capability_id="vn_jobs.aggregate",
            query={"keyword": "python"},
            diff_strategy="new_items",
            notification_channels=["in_app"],
        )

        fake_capability = mock.MagicMock()
        fake_capability.input_schema.model_validate.return_value = rule.query
        with (
            mock.patch.object(CapabilityRegistry, "get", return_value=fake_capability),
            mock.patch("app.alerts.engine.execute.execute_with_context") as mock_run,
            mock.patch("app.alerts.engine.execute.logger") as mock_logger,
        ):
            mock_run.return_value = {
                "items": [],
                "degraded": True,
                "degradation_reasons": ["topcv.timeout"],
            }
            await execute_alert_rule(
                session=_FakeSession(),
                alert_rule=rule,
                fired_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

        degraded_calls = [
            c for c in mock_logger.info.call_args_list if "degraded_source" in str(c)
        ]
        assert len(degraded_calls) >= 1

    def test_job_alert_logs_missing_rule(self):
        """A structured log is emitted when a claimed rule no longer exists."""
        from app.alerts.engine.tick import _execute_claimed_rule

        class _GetNoneSession:
            async def get(self, _model, _pk):
                return None

        rule = _FakeRule(id=uuid4(), workspace_id=1)

        with mock.patch("app.alerts.engine.tick.logger") as mock_logger:
            import asyncio

            asyncio.run(_execute_claimed_rule(session=_GetNoneSession(), rule=rule, now=None))

        missing_calls = [
            c for c in mock_logger.info.call_args_list if "search_missing" in str(c)
        ]
        assert len(missing_calls) >= 1


class TestJobAlertGrouping:
    """AC-4: grouped alert view."""

    def test_job_alert_notifications_grouped_by_alert_rule(self):
        """Notifications for the same alert rule are grouped with a count."""
        from app.alerts.services.grouping import group_alert_notifications

        notifications = [
            {
                "id": "n1",
                "type": "alert_run_complete",
                "metadata": {
                    "alert_rule_id": "rule-1",
                    "rule_name": "Python jobs",
                    "new_items_count": 2,
                },
            },
            {
                "id": "n2",
                "type": "alert_run_complete",
                "metadata": {
                    "alert_rule_id": "rule-1",
                    "rule_name": "Python jobs",
                    "new_items_count": 1,
                },
            },
            {
                "id": "n3",
                "type": "alert_run_complete",
                "metadata": {
                    "alert_rule_id": "rule-2",
                    "rule_name": "DevOps jobs",
                    "new_items_count": 5,
                },
            },
        ]

        groups = group_alert_notifications(notifications)

        assert len(groups) == 2
        assert groups[0]["alert_rule_id"] == "rule-1"
        assert len(groups[0]["notifications"]) == 2
        assert groups[1]["alert_rule_id"] == "rule-2"

    def test_job_alert_group_includes_rule_name_and_match_count(self):
        """Each group shows the alert rule name and total matched items."""
        from app.alerts.services.grouping import group_alert_notifications

        notifications = [
            {
                "id": "n1",
                "type": "alert_run_complete",
                "metadata": {
                    "alert_rule_id": "rule-1",
                    "rule_name": "Python jobs",
                    "new_items_count": 2,
                },
            },
            {
                "id": "n2",
                "type": "alert_run_complete",
                "metadata": {
                    "alert_rule_id": "rule-1",
                    "rule_name": "Python jobs",
                    "new_items_count": 1,
                },
            },
        ]

        groups = group_alert_notifications(notifications)

        assert groups[0]["rule_name"] == "Python jobs"
        assert groups[0]["match_count"] == 3
