"""Integration tests for automation-run Telegram notifications."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.runtime.executor import execute_run
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.schemas.definition.plan_step import PlanStep
from app.automations.services.telegram_notifications import (
    send_automation_run_telegram_notification,
)
from app.automations.tasks.notify_run_complete import notify_telegram_run_complete
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatHealthStatus,
    ExternalChatPlatform,
    Notification,
    User,
    Workspace,
)

pytestmark = pytest.mark.integration


async def _make_automation_and_run(
    session: AsyncSession,
    user: User,
    workspace: Workspace,
    *,
    status: RunStatus = RunStatus.SUCCEEDED,
    output: object = None,
    error: dict | None = None,
) -> AutomationRun:
    automation = Automation(
        name="Notify Test",
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        definition={},
    )
    session.add(automation)
    await session.flush()

    definition = AutomationDefinition(
        name="Notify Test",
        plan=[PlanStep(step_id="s1", action="noop", when="false")],
    )
    run = AutomationRun(
        automation_id=automation.id,
        status=status,
        definition_snapshot=definition.model_dump(),
        inputs={},
        output=output,
        error=error,
    )
    session.add(run)
    await session.flush()
    return run


async def _make_telegram_binding(
    session: AsyncSession,
    user: User,
    workspace: Workspace,
    *,
    account_suspended_at=None,
    account_health_status=None,
    binding_revoked_at=None,
    binding_suspended_at=None,
) -> ExternalChatBinding:
    account = ExternalChatAccount(
        platform=ExternalChatPlatform.TELEGRAM,
        mode=ExternalChatAccountMode.CLOUD_SHARED,
        is_system_account=True,
        health_status=account_health_status or ExternalChatHealthStatus.UNKNOWN,
    )
    if account_suspended_at is not None:
        account.suspended_at = account_suspended_at
    session.add(account)
    await session.flush()

    binding = ExternalChatBinding(
        account_id=account.id,
        user_id=user.id,
        workspace_id=workspace.id,
        state=ExternalChatBindingState.BOUND,
        external_peer_id="123456",
        revoked_at=binding_revoked_at,
        suspended_at=binding_suspended_at,
    )
    session.add(binding)
    await session.flush()
    return binding


async def test_execute_run_enqueues_notification_task(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    calls: list[dict] = []

    def _apply_async(*args, **kwargs) -> None:
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(notify_telegram_run_complete, "apply_async", _apply_async)

    run = await _make_automation_and_run(
        db_session, db_user, db_workspace, status=RunStatus.PENDING
    )
    await execute_run(db_session, run.id)

    assert run.status == RunStatus.SUCCEEDED
    assert len(calls) == 1
    assert calls[0]["kwargs"]["args"] == (run.id,)


async def test_send_notification_creates_in_app_notification_and_telegram(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    db_user.notification_preferences = {"automation_run_complete": {"telegram": True}}
    await _make_telegram_binding(db_session, db_user, db_workspace)

    sent: list[dict] = []

    class _FakeAdapter:
        def __init__(self, token: str) -> None:
            self.token = token

        async def send_message(
            self, *, external_peer_id, text, parse_mode=None, **kwargs
        ) -> None:
            sent.append(
                {"peer_id": external_peer_id, "text": text, "parse_mode": parse_mode}
            )

    import app.automations.services.telegram_notifications as tn_mod

    metrics: list[dict] = []
    monkeypatch.setattr(
        tn_mod, "record_gateway_outbound", lambda **kwargs: metrics.append(kwargs)
    )
    monkeypatch.setattr(tn_mod, "TelegramAdapter", _FakeAdapter)
    monkeypatch.setattr(tn_mod, "account_token", lambda account: "test-token")

    run = await _make_automation_and_run(db_session, db_user, db_workspace)
    await send_automation_run_telegram_notification(db_session, run.id)

    notification = (
        await db_session.execute(
            select(Notification).where(Notification.type == "automation_run_complete")
        )
    ).scalar_one_or_none()
    assert notification is not None
    assert notification.notification_metadata["run_id"] == run.id
    assert notification.notification_metadata["status"] == RunStatus.SUCCEEDED.value

    assert len(sent) == 1
    assert sent[0]["peer_id"] == "123456"
    assert sent[0]["parse_mode"] == "MarkdownV2"
    assert "[Open run]" in sent[0]["text"]
    assert metrics == [{"platform": "telegram", "kind": "send", "status": "sent"}]


async def test_send_notification_skips_telegram_when_preference_disabled(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    db_user.notification_preferences = {}
    await _make_telegram_binding(db_session, db_user, db_workspace)

    sent: list[dict] = []

    class _FakeAdapter:
        def __init__(self, token: str) -> None:
            self.token = token

        async def send_message(
            self, *, external_peer_id, text, parse_mode=None, **kwargs
        ) -> None:
            sent.append(
                {"peer_id": external_peer_id, "text": text, "parse_mode": parse_mode}
            )

    import app.automations.services.telegram_notifications as tn_mod

    metrics: list[dict] = []
    monkeypatch.setattr(
        tn_mod, "record_gateway_outbound", lambda **kwargs: metrics.append(kwargs)
    )
    monkeypatch.setattr(tn_mod, "TelegramAdapter", _FakeAdapter)
    monkeypatch.setattr(tn_mod, "account_token", lambda account: "test-token")

    run = await _make_automation_and_run(db_session, db_user, db_workspace)
    await send_automation_run_telegram_notification(db_session, run.id)

    notification = (
        await db_session.execute(
            select(Notification).where(Notification.type == "automation_run_complete")
        )
    ).scalar_one_or_none()
    assert notification is not None
    assert len(sent) == 0
    assert metrics == []


async def test_send_notification_telegram_failure_does_not_raise(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    db_user.notification_preferences = {"automation_run_complete": {"telegram": True}}
    await _make_telegram_binding(db_session, db_user, db_workspace)

    class _FailingAdapter:
        def __init__(self, token: str) -> None:
            self.token = token

        async def send_message(self, **kwargs) -> None:
            raise RuntimeError("Telegram API down")

    import app.automations.services.telegram_notifications as tn_mod

    metrics: list[dict] = []
    monkeypatch.setattr(
        tn_mod, "record_gateway_outbound", lambda **kwargs: metrics.append(kwargs)
    )
    monkeypatch.setattr(tn_mod, "TelegramAdapter", _FailingAdapter)
    monkeypatch.setattr(tn_mod, "account_token", lambda account: "test-token")

    run = await _make_automation_and_run(db_session, db_user, db_workspace)
    await send_automation_run_telegram_notification(db_session, run.id)

    notification = (
        await db_session.execute(
            select(Notification).where(Notification.type == "automation_run_complete")
        )
    ).scalar_one_or_none()
    assert notification is not None
    assert metrics == [{"platform": "telegram", "kind": "send", "status": "failed"}]


async def test_send_notification_skips_suspended_binding(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    db_user.notification_preferences = {"automation_run_complete": {"telegram": True}}
    await _make_telegram_binding(
        db_session,
        db_user,
        db_workspace,
        binding_suspended_at=datetime.now(UTC),
    )

    sent: list[dict] = []

    class _FakeAdapter:
        def __init__(self, token: str) -> None:
            self.token = token

        async def send_message(
            self, *, external_peer_id, text, parse_mode=None, **kwargs
        ) -> None:
            sent.append(
                {"peer_id": external_peer_id, "text": text, "parse_mode": parse_mode}
            )

    import app.automations.services.telegram_notifications as tn_mod

    metrics: list[dict] = []
    monkeypatch.setattr(
        tn_mod, "record_gateway_outbound", lambda **kwargs: metrics.append(kwargs)
    )
    monkeypatch.setattr(tn_mod, "TelegramAdapter", _FakeAdapter)
    monkeypatch.setattr(tn_mod, "account_token", lambda account: "test-token")

    run = await _make_automation_and_run(db_session, db_user, db_workspace)
    await send_automation_run_telegram_notification(db_session, run.id)

    notification = (
        await db_session.execute(
            select(Notification).where(Notification.type == "automation_run_complete")
        )
    ).scalar_one_or_none()
    assert notification is not None
    assert len(sent) == 0
    assert metrics == []


async def test_send_notification_skips_failing_telegram_account(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    db_user.notification_preferences = {"automation_run_complete": {"telegram": True}}
    await _make_telegram_binding(
        db_session,
        db_user,
        db_workspace,
        account_health_status=ExternalChatHealthStatus.FAILING,
    )

    sent: list[dict] = []

    class _FakeAdapter:
        def __init__(self, token: str) -> None:
            self.token = token

        async def send_message(
            self, *, external_peer_id, text, parse_mode=None, **kwargs
        ) -> None:
            sent.append(
                {"peer_id": external_peer_id, "text": text, "parse_mode": parse_mode}
            )

    import app.automations.services.telegram_notifications as tn_mod

    metrics: list[dict] = []
    monkeypatch.setattr(
        tn_mod, "record_gateway_outbound", lambda **kwargs: metrics.append(kwargs)
    )
    monkeypatch.setattr(tn_mod, "TelegramAdapter", _FakeAdapter)
    monkeypatch.setattr(tn_mod, "account_token", lambda account: "test-token")

    run = await _make_automation_and_run(db_session, db_user, db_workspace)
    await send_automation_run_telegram_notification(db_session, run.id)

    notification = (
        await db_session.execute(
            select(Notification).where(Notification.type == "automation_run_complete")
        )
    ).scalar_one_or_none()
    assert notification is not None
    assert len(sent) == 0
    assert metrics == []
