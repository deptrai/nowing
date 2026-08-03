"""Integration tests for Telegram inbound command and callback dispatch."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatEventKind,
    ExternalChatEventStatus,
    ExternalChatInboundEvent,
    ExternalChatPeerKind,
    ExternalChatPlatform,
)
from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.inbox_processor import process_inbound_event
from app.gateway.registry import PlatformBundle
from app.gateway.telegram.commands import TelegramGatewayCommands

pytestmark = pytest.mark.integration


class _TestSessionContext:
    """Context manager that yields an existing test session without closing it."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _session_maker(session: AsyncSession):
    return _TestSessionContext(session)


def _message_payload(*, text: str, peer_id: str = "12345") -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": int(peer_id), "type": "private"},
            "from": {"id": 111, "first_name": "Test", "username": "testuser"},
            "text": text,
        },
    }


def _callback_payload(
    *,
    data: str,
    peer_id: str = "12345",
    callback_query_id: str = "cq1",
) -> dict[str, Any]:
    return {
        "update_id": 2,
        "callback_query": {
            "id": callback_query_id,
            "from": {"id": 111, "first_name": "Test", "username": "testuser"},
            "message": {
                "message_id": 1,
                "chat": {"id": int(peer_id), "type": "private"},
            },
            "data": data,
        },
    }


def _parsed_message(*, text: str, peer_id: str = "12345") -> ParsedInboundEvent:
    return ParsedInboundEvent(
        platform="telegram",
        event_kind="message",
        external_peer_id=peer_id,
        external_peer_kind="direct",
        external_message_id="1",
        external_user_id="111",
        text=text,
        raw_payload={},
        display_name="Test",
        username="testuser",
        metadata={"update_id": 1, "chat_type": "private"},
    )


def _parsed_callback(
    *,
    data: str,
    peer_id: str = "12345",
    callback_query_id: str = "cq1",
) -> ParsedInboundEvent:
    return ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id=peer_id,
        external_peer_kind="direct",
        external_message_id="1",
        external_user_id="111",
        text=data,
        raw_payload={},
        display_name="Test",
        username="testuser",
        metadata={
            "callback_query_id": callback_query_id,
            "chat_type": "private",
            "update_id": 2,
        },
    )


@pytest.fixture
def telegram_bundle(mocker):
    """Provide a mocked Telegram bundle for inbox processing."""
    adapter = MagicMock()
    adapter.send_message = AsyncMock()
    adapter.edit_message = AsyncMock()
    adapter.answer_callback_query = AsyncMock()
    adapter.leave_chat = AsyncMock()
    adapter.parse_inbound = MagicMock()

    launch_run_mock = mocker.patch(
        "app.gateway.telegram.commands.launch_run", new=AsyncMock()
    )
    acquire_token_mock = mocker.patch(
        "app.gateway.telegram.commands.acquire_token",
        new=AsyncMock(return_value=0),
    )

    bundle = PlatformBundle(
        adapter=adapter,
        commands=TelegramGatewayCommands(),
        platform_label="telegram",
        translator_factory=lambda _adapter, _event: MagicMock(),
        auto_bind_owner=False,
    )
    mocker.patch(
        "app.gateway.inbox_processor.resolve_platform_bundle", return_value=bundle
    )

    return SimpleNamespace(
        adapter=adapter,
        bundle=bundle,
        launch_run_mock=launch_run_mock,
        acquire_token_mock=acquire_token_mock,
    )


async def _telegram_account(db_session: AsyncSession) -> ExternalChatAccount:
    account = ExternalChatAccount(
        platform=ExternalChatPlatform.TELEGRAM,
        mode=ExternalChatAccountMode.CLOUD_SHARED,
        is_system_account=True,
        bot_username="TestBot",
        webhook_secret="secret",
        cursor_state={},
    )
    db_session.add(account)
    await db_session.flush()
    return account


async def _bound_binding(
    db_session: AsyncSession,
    account: ExternalChatAccount,
    user,
    workspace,
    *,
    peer_id: str = "12345",
    state: ExternalChatBindingState = ExternalChatBindingState.BOUND,
) -> ExternalChatBinding:
    binding = ExternalChatBinding(
        account_id=account.id,
        user_id=user.id,
        workspace_id=workspace.id,
        state=state,
        external_peer_id=peer_id,
        external_peer_kind=ExternalChatPeerKind.DIRECT,
    )
    db_session.add(binding)
    await db_session.flush()
    return binding


async def _active_automation(
    db_session: AsyncSession, workspace, *, name: str = "Test Automation"
) -> Automation:
    automation = Automation(
        workspace_id=workspace.id,
        created_by_user_id=None,
        name=name,
        definition={"steps": []},
        status=AutomationStatus.ACTIVE,
    )
    db_session.add(automation)
    await db_session.flush()
    return automation


async def _succeeded_run(
    db_session: AsyncSession, automation: Automation
) -> AutomationRun:
    run = AutomationRun(
        automation_id=automation.id,
        status=RunStatus.SUCCEEDED,
        definition_snapshot={},
        inputs={},
        step_results=[],
        artifacts=[],
        finished_at=datetime.now(UTC),
    )
    db_session.add(run)
    await db_session.flush()
    return run


async def _inbound_event(
    db_session: AsyncSession,
    account: ExternalChatAccount,
    raw_payload: dict[str, Any],
    *,
    kind: ExternalChatEventKind,
    peer_id: str,
    message_id: str = "1",
) -> ExternalChatInboundEvent:
    event = ExternalChatInboundEvent(
        account_id=account.id,
        platform=ExternalChatPlatform.TELEGRAM,
        event_dedupe_key=f"test-{uuid4()}",
        external_event_id="1",
        external_message_id=message_id,
        event_kind=kind,
        raw_payload=raw_payload,
        status=ExternalChatEventStatus.RECEIVED,
    )
    db_session.add(event)
    await db_session.commit()
    return event


@pytest.mark.asyncio
async def test_status_command_dispatch(
    db_session: AsyncSession, db_user, db_workspace, telegram_bundle
):
    """A bound user sending /status sees the latest run for the workspace."""
    account = await _telegram_account(db_session)
    await _bound_binding(db_session, account, db_user, db_workspace)
    automation = await _active_automation(
        db_session, db_workspace, name="Latest Automation"
    )
    await _succeeded_run(db_session, automation)

    peer_id = "12345"
    raw = _message_payload(text="/status", peer_id=peer_id)
    telegram_bundle.adapter.parse_inbound.return_value = _parsed_message(
        text="/status", peer_id=peer_id
    )
    event = await _inbound_event(
        db_session,
        account,
        raw,
        kind=ExternalChatEventKind.MESSAGE,
        peer_id=peer_id,
    )

    await process_inbound_event(
        event.id, session_maker=lambda: _session_maker(db_session)
    )

    await db_session.refresh(event)
    assert event.status == ExternalChatEventStatus.PROCESSED
    telegram_bundle.adapter.send_message.assert_awaited()
    text = telegram_bundle.adapter.send_message.call_args.kwargs["text"]
    assert "Latest Automation" in text


@pytest.mark.asyncio
async def test_run_command_dispatch(
    db_session: AsyncSession, db_user, db_workspace, telegram_bundle
):
    """A bound user sending /run <name> triggers launch_run and gets a confirmation."""
    account = await _telegram_account(db_session)
    peer_id = "12346"
    await _bound_binding(db_session, account, db_user, db_workspace, peer_id=peer_id)
    await _active_automation(db_session, db_workspace, name="Run This")

    raw = _message_payload(text="/run Run This", peer_id=peer_id)
    telegram_bundle.adapter.parse_inbound.return_value = _parsed_message(
        text="/run Run This", peer_id=peer_id
    )
    event = await _inbound_event(
        db_session,
        account,
        raw,
        kind=ExternalChatEventKind.MESSAGE,
        peer_id=peer_id,
    )

    await process_inbound_event(
        event.id, session_maker=lambda: _session_maker(db_session)
    )

    await db_session.refresh(event)
    assert event.status == ExternalChatEventStatus.PROCESSED
    telegram_bundle.launch_run_mock.assert_awaited_once()
    telegram_bundle.adapter.send_message.assert_awaited()
    text = telegram_bundle.adapter.send_message.call_args.kwargs["text"]
    assert "Run started" in text


@pytest.mark.asyncio
async def test_run_command_bot_mention_only_lists_automations(
    db_session: AsyncSession, db_user, db_workspace, telegram_bundle
):
    """/run with only a bot mention is treated as a list request."""
    account = await _telegram_account(db_session)
    peer_id = "12347"
    await _bound_binding(db_session, account, db_user, db_workspace, peer_id=peer_id)
    await _active_automation(db_session, db_workspace, name="Automation A")
    await _active_automation(db_session, db_workspace, name="Automation B")

    raw = _message_payload(text="/run @TestBot", peer_id=peer_id)
    telegram_bundle.adapter.parse_inbound.return_value = _parsed_message(
        text="/run @TestBot", peer_id=peer_id
    )
    event = await _inbound_event(
        db_session,
        account,
        raw,
        kind=ExternalChatEventKind.MESSAGE,
        peer_id=peer_id,
    )

    await process_inbound_event(
        event.id, session_maker=lambda: _session_maker(db_session)
    )

    await db_session.refresh(event)
    assert event.status == ExternalChatEventStatus.PROCESSED
    telegram_bundle.launch_run_mock.assert_not_awaited()
    telegram_bundle.adapter.send_message.assert_awaited()
    text = telegram_bundle.adapter.send_message.call_args.kwargs["text"]
    assert "Automation A" in text
    assert "Automation B" in text


@pytest.mark.asyncio
async def test_callback_view_run_dispatch(
    db_session: AsyncSession, db_user, db_workspace, telegram_bundle
):
    """A callback query view_run:<id> edits the message with a run summary."""
    account = await _telegram_account(db_session)
    peer_id = "12348"
    await _bound_binding(db_session, account, db_user, db_workspace, peer_id=peer_id)
    automation = await _active_automation(
        db_session, db_workspace, name="Callback Automation"
    )
    run = await _succeeded_run(db_session, automation)

    raw = _callback_payload(
        data=f"view_run:{run.id}", peer_id=peer_id, callback_query_id="cq1"
    )
    telegram_bundle.adapter.parse_inbound.return_value = _parsed_callback(
        data=f"view_run:{run.id}", peer_id=peer_id, callback_query_id="cq1"
    )
    event = await _inbound_event(
        db_session,
        account,
        raw,
        kind=ExternalChatEventKind.CALLBACK_QUERY,
        peer_id=peer_id,
        message_id="1",
    )

    await process_inbound_event(
        event.id, session_maker=lambda: _session_maker(db_session)
    )

    await db_session.refresh(event)
    assert event.status == ExternalChatEventStatus.PROCESSED
    telegram_bundle.adapter.answer_callback_query.assert_awaited()
    telegram_bundle.adapter.edit_message.assert_awaited()
    text = telegram_bundle.adapter.edit_message.call_args.kwargs["text"]
    assert "Callback Automation" in text


@pytest.mark.asyncio
async def test_unbound_message_onboarding(db_session: AsyncSession, telegram_bundle):
    """An unbound chat receives onboarding and the event is marked ignored."""
    account = await _telegram_account(db_session)

    peer_id = "12349"
    raw = _message_payload(text="/status", peer_id=peer_id)
    telegram_bundle.adapter.parse_inbound.return_value = _parsed_message(
        text="/status", peer_id=peer_id
    )
    event = await _inbound_event(
        db_session,
        account,
        raw,
        kind=ExternalChatEventKind.MESSAGE,
        peer_id=peer_id,
    )

    await process_inbound_event(
        event.id, session_maker=lambda: _session_maker(db_session)
    )

    await db_session.refresh(event)
    assert event.status == ExternalChatEventStatus.IGNORED
    assert event.last_error == "unbound_chat"
    telegram_bundle.adapter.send_message.assert_awaited()
    text = telegram_bundle.adapter.send_message.call_args.kwargs["text"]
    assert "pairing code" in text.lower()


@pytest.mark.asyncio
async def test_unbound_callback_query_is_answered(
    db_session: AsyncSession, telegram_bundle
):
    """A callback query in an unbound chat has its spinner cleared and is not retried."""
    account = await _telegram_account(db_session)

    peer_id = "12350"
    raw = _callback_payload(data="view_run:1", peer_id=peer_id, callback_query_id="cq1")
    telegram_bundle.adapter.parse_inbound.return_value = _parsed_callback(
        data="view_run:1", peer_id=peer_id, callback_query_id="cq1"
    )
    event = await _inbound_event(
        db_session,
        account,
        raw,
        kind=ExternalChatEventKind.CALLBACK_QUERY,
        peer_id=peer_id,
        message_id="1",
    )

    await process_inbound_event(
        event.id, session_maker=lambda: _session_maker(db_session)
    )

    await db_session.refresh(event)
    assert event.status == ExternalChatEventStatus.PROCESSED
    assert event.last_error == "unbound_callback"
    telegram_bundle.adapter.answer_callback_query.assert_awaited_with(
        callback_query_id="cq1"
    )
    telegram_bundle.adapter.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_suspended_binding_rejected(
    db_session: AsyncSession, db_user, db_workspace, telegram_bundle
):
    """A SUSPENDED binding is rejected before any command/callback handler runs."""
    account = await _telegram_account(db_session)
    await _bound_binding(
        db_session,
        account,
        db_user,
        db_workspace,
        peer_id="12351",
        state=ExternalChatBindingState.SUSPENDED,
    )

    peer_id = "12351"
    raw = _message_payload(text="/status", peer_id=peer_id)
    telegram_bundle.adapter.parse_inbound.return_value = _parsed_message(
        text="/status", peer_id=peer_id
    )
    event = await _inbound_event(
        db_session,
        account,
        raw,
        kind=ExternalChatEventKind.MESSAGE,
        peer_id=peer_id,
    )

    await process_inbound_event(
        event.id, session_maker=lambda: _session_maker(db_session)
    )

    await db_session.refresh(event)
    assert event.status == ExternalChatEventStatus.IGNORED
    assert event.last_error == "suspended_binding"
    telegram_bundle.adapter.send_message.assert_awaited()
    text = telegram_bundle.adapter.send_message.call_args.kwargs["text"]
    assert "suspended" in text.lower()
