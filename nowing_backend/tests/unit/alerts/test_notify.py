"""Unit tests for alert notification dispatch."""

from __future__ import annotations

from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from app.alerts.engine.notify import (
    _notification_message,
    _notification_title,
    notify_alert_run,
)

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


class _FakeSession:
    def __init__(self, subscriptions: list[_FakeSub] | None = None):
        self.subscriptions = subscriptions or []

    async def execute(self, _stmt):
        return _FakeResult(self.subscriptions)


def test_notification_title_and_message():
    rule = _FakeRule(name="Python jobs", workspace_id=1, id=uuid4())
    snapshot = _FakeSnapshot(
        id=uuid4(),
        run_status="succeeded",
        new_items_count=2,
        degradation_reasons=None,
    )

    assert _notification_title(rule, snapshot) == "Alert 'Python jobs' 2 matched items"
    assert "matched 2 item(s)" in _notification_message(rule, snapshot)
    assert "saved-searches" in _notification_message(rule, snapshot)


@pytest.mark.asyncio
async def test_notify_skips_non_rule_channels():
    rule = _FakeRule(
        id=uuid4(),
        workspace_id=1,
        name="Python jobs",
        notification_channels=["in_app"],
    )
    snapshot = _FakeSnapshot(
        run_status="succeeded",
        new_items_count=0,
        degradation_reasons=None,
    )
    sub = _FakeSub(
        user_id=uuid4(),
        alert_rule_id=rule.id,
        enabled=True,
        channels=["telegram"],  # not in rule channels
    )
    session = _FakeSession([sub])

    with mock.patch(
        "app.alerts.engine.notify.NotificationService.create_notification",
        new=mock.AsyncMock(),
    ) as mock_create:
        await notify_alert_run(session=session, alert_rule=rule, snapshot=snapshot)

    mock_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_creates_in_app_notification():
    rule = _FakeRule(
        id=uuid4(),
        workspace_id=1,
        name="Python jobs",
        notification_channels=["in_app"],
    )
    snapshot = _FakeSnapshot(
        id=uuid4(),
        run_status="succeeded",
        new_items_count=1,
        degradation_reasons=None,
    )
    user_id = uuid4()
    sub = _FakeSub(
        user_id=user_id,
        alert_rule_id=rule.id,
        enabled=True,
        channels=[],
    )
    session = _FakeSession([sub])

    with mock.patch(
        "app.alerts.engine.notify.NotificationService.create_notification",
        new=mock.AsyncMock(),
    ) as mock_create:
        await notify_alert_run(session=session, alert_rule=rule, snapshot=snapshot)

    mock_create.assert_awaited_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["user_id"] == user_id
    assert call_kwargs["workspace_id"] == 1
    assert call_kwargs["notification_type"] == "alert_run_complete"


def test_notification_message_bounds_large_degradation_reasons():
    """Verify that more than 3 degradation reasons are capped with (+N more)."""
    rule = _FakeRule(name="Test Rule", workspace_id=1, id=uuid4())
    snapshot = _FakeSnapshot(
        id=uuid4(),
        run_status="degraded",
        degradation_reasons=["reason_1", "reason_2", "reason_3", "reason_4", "reason_5"],
    )

    msg = _notification_message(rule, snapshot)
    assert "reason_1, reason_2, reason_3 (+2 more)" in msg


def test_send_email_smtp_ssl_mode(monkeypatch):
    """Verify SMTP_SSL is used when SMTP_SSL config is True or port is 465."""
    from app.alerts.engine.notify import _send_email_smtp

    monkeypatch.setattr("app.config.config.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.config.config.SMTP_PORT", 465)
    monkeypatch.setattr("app.config.config.SMTP_SSL", True, raising=False)
    monkeypatch.setattr("app.config.config.SMTP_USER", "")
    monkeypatch.setattr("app.config.config.SMTP_PASSWORD", "")

    mock_server = mock.MagicMock()
    with mock.patch("smtplib.SMTP_SSL", return_value=mock_server) as mock_ssl:
        _send_email_smtp("test@example.com", "Subject", "Body")
        mock_ssl.assert_called_once()
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()
