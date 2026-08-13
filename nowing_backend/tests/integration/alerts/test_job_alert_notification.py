"""Integration tests for Story 12.9 — Job Market Alerts.

End-to-end: saved search rule -> run -> diff -> in-app notification with a
deep link, degraded-source skip, and scheduler continuation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.engine.execute import execute_alert_rule
from app.alerts.engine.tick import _claim_due_rules, _execute_claimed_rule
from app.alerts.schemas import AlertRuleCreate
from app.alerts.services import create_alert_rule
from app.db import AlertSnapshot, Notification, User, Workspace

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _FakeInput(BaseModel):
    keyword: str


class _FakeOutput(BaseModel):
    items: list[dict[str, Any]]
    degraded: bool = False
    degradation_reasons: list[str] | None = None


def _fake_capability(outputs: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(
        name="vn_jobs.aggregate",
        input_schema=_FakeInput,
        executor=mock.AsyncMock(side_effect=outputs),
    )


async def _list_alert_notifications(
    session: AsyncSession, user_id: Any
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


class TestJobAlertLifecycle:
    """End-to-end: saved search → run → notification."""

    async def test_job_alert_lifecycle_creates_in_app_notification(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """AC-2: a new posting creates an in-app notification."""
        rule = await create_alert_rule(
            session=db_session,
            workspace_id=db_workspace.id,
            client_id=None,
            user_id=db_user.id,
            data=AlertRuleCreate(
                name="Python jobs",
                capability_id="vn_jobs.aggregate",
                query={"keyword": "python"},
                schedule="none",
                timezone="UTC",
                notification_channels=["in_app"],
            ),
        )

        fake_cap = _fake_capability(
            [
                _FakeOutput(items=[{"id": "job-1", "title": "Senior Python"}]),
                _FakeOutput(
                    items=[
                        {"id": "job-1", "title": "Senior Python"},
                        {"id": "job-2", "title": "ML Engineer"},
                    ]
                ),
            ]
        )
        with mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get", return_value=fake_cap
        ):
            first = await execute_alert_rule(
                session=db_session,
                alert_rule=rule,
                fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            )
            second = await execute_alert_rule(
                session=db_session,
                alert_rule=rule,
                fired_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
            )

        # Baseline first run: no notification.
        assert first.new_items_count == 0
        # Second run detects one new posting -> notification.
        assert second.new_items_count == 1

        notifications = await _list_alert_notifications(db_session, db_user.id)
        assert len(notifications) >= 1
        alert_notifications = [
            n for n in notifications if n.type == "alert_run_complete"
        ]
        assert len(alert_notifications) >= 1
        meta = alert_notifications[0].notification_metadata or {}
        assert meta.get("alert_rule_id") == str(rule.id)
        assert meta.get("rule_name") == "Python jobs"
        assert meta.get("new_items_count") == 1

    async def test_job_alert_click_navigates_to_saved_search_results(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """AC-3: the notification deep link points at the saved search + snapshot."""
        rule = await create_alert_rule(
            session=db_session,
            workspace_id=db_workspace.id,
            client_id=None,
            user_id=db_user.id,
            data=AlertRuleCreate(
                name="Python jobs",
                capability_id="vn_jobs.aggregate",
                query={"keyword": "python"},
                schedule="none",
                timezone="UTC",
                notification_channels=["in_app"],
            ),
        )

        fake_cap = _fake_capability(
            [
                _FakeOutput(items=[{"id": "job-1", "title": "Senior Python"}]),
                _FakeOutput(
                    items=[
                        {"id": "job-1", "title": "Senior Python"},
                        {"id": "job-2", "title": "ML Engineer"},
                    ]
                ),
            ]
        )
        with mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get", return_value=fake_cap
        ):
            await execute_alert_rule(
                session=db_session,
                alert_rule=rule,
                fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            )
            snap = await execute_alert_rule(
                session=db_session,
                alert_rule=rule,
                fired_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
            )

        notifications = await _list_alert_notifications(db_session, db_user.id)
        alert_notifications = [
            n for n in notifications if n.type == "alert_run_complete"
        ]
        assert len(alert_notifications) >= 1

        message = alert_notifications[0].message
        expected_path = (
            f"/dashboard/{db_workspace.id}/research/saved-searches/{rule.id}"
        )
        assert expected_path in message
        assert f"snapshot={snap.id}" in message

        # The snapshot the deep link points to is queryable (page can load it).
        stored = (
            await db_session.execute(
                select(AlertSnapshot).where(AlertSnapshot.id == snap.id)
            )
        ).scalar_one_or_none()
        assert stored is not None
        assert stored.new_items_count == 1


class TestJobAlertDegradedSource:
    """Degraded source handling end-to-end."""

    async def test_job_alert_degraded_source_skips_notification(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """AC-5: degraded + no new items -> no notification."""
        rule = await create_alert_rule(
            session=db_session,
            workspace_id=db_workspace.id,
            client_id=None,
            user_id=db_user.id,
            data=AlertRuleCreate(
                name="Python jobs",
                capability_id="vn_jobs.aggregate",
                query={"keyword": "python"},
                schedule="none",
                timezone="UTC",
                notification_channels=["in_app"],
            ),
        )

        fake_cap = _fake_capability(
            [
                _FakeOutput(
                    items=[],
                    degraded=True,
                    degradation_reasons=["topcv.timeout"],
                ),
                _FakeOutput(
                    items=[],
                    degraded=True,
                    degradation_reasons=["topcv.timeout"],
                ),
            ]
        )
        with mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get", return_value=fake_cap
        ):
            first = await execute_alert_rule(
                session=db_session,
                alert_rule=rule,
                fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            )
            second = await execute_alert_rule(
                session=db_session,
                alert_rule=rule,
                fired_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
            )

        assert first.run_status == "degraded"
        assert second.run_status == "degraded"
        assert second.new_items_count == 0

        notifications = await _list_alert_notifications(db_session, db_user.id)
        assert all(n.type != "alert_run_complete" for n in notifications)

    async def test_job_alert_scheduler_continues_after_degraded_run(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
    ) -> None:
        """AC-5: after a degraded run, the rule stays enabled and next_fire_at advances."""
        rule = await create_alert_rule(
            session=db_session,
            workspace_id=db_workspace.id,
            client_id=None,
            user_id=db_user.id,
            data=AlertRuleCreate(
                name="Python jobs",
                capability_id="vn_jobs.aggregate",
                query={"keyword": "python"},
                schedule="daily",
                timezone="UTC",
                notification_channels=["in_app"],
            ),
        )
        # Force the rule to be due immediately.
        rule.next_fire_at = datetime.now(UTC) - timedelta(minutes=5)
        await db_session.commit()

        fake_cap = _fake_capability(
            [
                _FakeOutput(
                    items=[],
                    degraded=True,
                    degradation_reasons=["topcv.timeout"],
                )
            ]
        )
        now = datetime.now(UTC)
        with mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get", return_value=fake_cap
        ):
            claims = await _claim_due_rules(db_session, now=now)
            assert len(claims) == 1
            for claimed in claims:
                await _execute_claimed_rule(db_session, claimed, now=now)

        await db_session.refresh(rule)
        assert rule.enabled is True
        assert rule.next_fire_at is not None
        assert rule.next_fire_at > now
