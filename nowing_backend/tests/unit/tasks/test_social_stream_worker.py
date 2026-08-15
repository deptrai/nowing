"""Unit tests for social stream worker alert matching and lead creation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

import pytest

from app.alerts.persistence.models.alert_rule import AlertRule
from app.db import User
from app.tasks.social_stream_worker import (
    SocialPostEvent,
    _create_lead_from_social_post,
    _evaluate_alerts_for_social_post,
)


@pytest.fixture
def fake_event():
    return SocialPostEvent(
        platform="facebook",
        external_post_id="fb_001",
        content="Cần bán nhà Quận 1 giá 5 tỷ, LH 0912345678",
        author_id="usr_1",
        author_name="Test Author",
        post_url="https://facebook.com/posts/fb_001",
        target_id=1,
        workspace_id=1,
    )


@pytest.fixture
def fake_extracted():
    return {
        "phones": ["0912345678"],
        "emails": [],
        "prices": [],
        "locations": ["Quận 1"],
        "intent": "sell",
    }


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, rows=None, target=None, workspace=None, existing_lead_id=None):
        self._rows = rows or []
        self._target = target
        self._workspace = workspace
        self._existing_lead_id = existing_lead_id
        self.added = []
        self.committed = 0

    async def get(self, model, _id):
        if model.__name__ == "SocialMonitoredTarget":
            return self._target
        if model.__name__ == "Workspace":
            return self._workspace
        if model.__name__ == "Lead":
            return None
        if model.__name__ == "User":
            return User(
                id=uuid4(),
                email="test@nowing.net",
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        return None

    async def scalar(self, _stmt):
        return self._existing_lead_id

    async def execute(self, _stmt):
        return _FakeResult(self._rows)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        pass


@pytest.mark.asyncio
async def test_evaluate_alerts_for_social_post_triggers_alert_rule(
    fake_event,
    fake_extracted,
):
    """When content matches a rule, the worker executes the alert rule."""
    rule = AlertRule(
        id=uuid4(),
        workspace_id=1,
        client_id=None,
        name="Bán nhà Quận 1",
        capability_id="social.search_leads",
        query={"keyword": "Quận 1"},
        schedule="none",
        timezone="UTC",
        cron="",
        next_fire_at=None,
        last_fired_at=None,
        diff_strategy="new_items",
        threshold=None,
        notification_channels=["in_app"],
        enabled=True,
    )
    session = _FakeSession(rows=[rule])

    with mock.patch(
        "app.tasks.social_stream_worker.execute_alert_rule", new=mock.AsyncMock()
    ) as mock_execute:
        await _evaluate_alerts_for_social_post(
            session=session,
            event=fake_event,
            raw_entities=fake_extracted,
            fit_score=0.75,
        )

    assert mock_execute.await_count == 1
    assert mock_execute.await_args.kwargs["alert_rule"] is rule


@pytest.mark.asyncio
async def test_create_lead_from_social_post_skips_existing_lead(
    fake_event,
    fake_extracted,
):
    """Duplicate lead by source_url is not re-created."""
    session = _FakeSession(
        existing_lead_id=uuid4(),
        target=SimpleNamespace(workspace_id=1, target_name="Hanoi BDS"),
    )

    lead = await _create_lead_from_social_post(
        session=session,
        event=fake_event,
        raw_entities=fake_extracted,
        fit_score=0.75,
    )

    assert lead is None
    assert session.added == []
