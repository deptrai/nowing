"""Unit tests for alert engine tick task."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from app.alerts.engine.tick import _claim_due_rules, _self_heal_null_next_fire

pytestmark = pytest.mark.unit


class _FakeRule:
    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Result:
    def __init__(self, rules: list[_FakeRule]):
        self.rules = rules

    def scalars(self):
        return self

    def all(self):
        return self.rules


class _FakeSession:
    def __init__(self, rules: list[_FakeRule] | None = None):
        self.rules = rules or []
        self.committed = 0

    async def execute(self, _stmt):
        return _Result(self.rules)

    async def commit(self):
        self.committed += 1


@pytest.mark.asyncio
async def test_claim_due_rules_advances_next_fire():
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    rule = _FakeRule(
        id=uuid4(),
        enabled=True,
        cron="0 0 * * *",
        timezone="UTC",
        next_fire_at=now,
        last_fired_at=None,
    )
    session = _FakeSession([rule])

    with mock.patch(
        "app.alerts.engine.tick.compute_next_fire_at",
        return_value=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
    ):
        claimed = await _claim_due_rules(session, now=now)

    assert len(claimed) == 1
    assert rule.last_fired_at == now
    assert rule.next_fire_at == datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    assert session.committed == 1


@pytest.mark.asyncio
async def test_self_heal_backfills_null_next_fire():
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    rule = _FakeRule(
        id=uuid4(),
        enabled=True,
        cron="0 0 * * *",
        timezone="UTC",
        next_fire_at=None,
    )
    session = _FakeSession([rule])

    with mock.patch(
        "app.alerts.engine.tick.compute_next_fire_at",
        return_value=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
    ):
        await _self_heal_null_next_fire(session, now=now)

    assert rule.next_fire_at == datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    assert session.committed == 1
