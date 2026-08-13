"""Unit tests for alert rule execution."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.alerts.engine.execute import execute_alert_rule

pytestmark = pytest.mark.unit


class _FakeInput(BaseModel):
    keyword: str


class _FakeOutput(BaseModel):
    items: list[dict[str, Any]]
    degraded: bool = False
    degradation_reasons: list[str] | None = None


@pytest.fixture
def fake_alert_rule():
    from app.alerts.persistence.models.alert_rule import AlertRule

    return AlertRule(
        id=uuid4(),
        workspace_id=1,
        client_id=None,
        capability_id="test.jobs",
        name="Python jobs",
        query={"keyword": "python"},
        schedule="daily",
        timezone="UTC",
        cron="0 0 * * *",
        diff_strategy="new_items",
        notification_channels=["in_app"],
        enabled=True,
    )


class _FakeSession:
    """Minimal async session stand-in for unit tests."""

    def __init__(self):
        self.added: list[Any] = []
        self.committed = 0

    async def execute(self, _stmt):
        class _Result:
            def scalars(self):
                return self

            def first(self):
                return None

            def all(self):
                return []

        return _Result()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        pass


@pytest.mark.asyncio
async def test_execute_creates_snapshot(fake_alert_rule):
    fake_cap = SimpleNamespace(
        name="test.jobs",
        input_schema=_FakeInput,
        executor=mock.AsyncMock(
            return_value=_FakeOutput(items=[{"id": "job-1", "title": "Senior Python"}])
        ),
    )
    session = _FakeSession()

    with (
        mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get",
            return_value=fake_cap,
        ),
        mock.patch("app.alerts.engine.execute.notify_alert_run", new=mock.AsyncMock()),
    ):
        snapshot = await execute_alert_rule(
            session=session,
            alert_rule=fake_alert_rule,
            fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )

    assert snapshot is not None
    assert snapshot.run_status == "succeeded"
    assert snapshot.snapshot_json["source_ids"] == ["job-1"]
    fake_cap.executor.assert_awaited_once()
    assert session.committed >= 1


@pytest.mark.asyncio
async def test_execute_rejects_item_without_id(fake_alert_rule):
    fake_cap = SimpleNamespace(
        name="test.jobs",
        input_schema=_FakeInput,
        executor=mock.AsyncMock(
            return_value=_FakeOutput(items=[{"title": "No id"}])
        ),
    )
    session = _FakeSession()

    with (
        mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get",
            return_value=fake_cap,
        ),
        mock.patch("app.alerts.engine.execute.notify_alert_run", new=mock.AsyncMock()),
        pytest.raises(ValueError, match="no id/source_id/canonical_id"),
    ):
        await execute_alert_rule(
            session=session,
            alert_rule=fake_alert_rule,
            fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_execute_rejects_non_dict_item(fake_alert_rule):
    class _BadOutput(BaseModel):
        items: list[Any]

    fake_cap = SimpleNamespace(
        name="test.jobs",
        input_schema=_FakeInput,
        executor=mock.AsyncMock(return_value=_BadOutput(items=["not-a-dict"])),
    )
    session = _FakeSession()

    with (
        mock.patch(
            "app.alerts.engine.execute.CapabilityRegistry.get",
            return_value=fake_cap,
        ),
        mock.patch("app.alerts.engine.execute.notify_alert_run", new=mock.AsyncMock()),
        pytest.raises(ValueError, match="is not a dict"),
    ):
        await execute_alert_rule(
            session=session,
            alert_rule=fake_alert_rule,
            fired_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )
