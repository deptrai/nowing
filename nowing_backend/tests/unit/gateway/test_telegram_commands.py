"""Tests for Telegram bot /status and /run commands."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.automations.dispatch.errors import DispatchError
from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.db import ExternalChatBinding
from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.telegram.commands import TelegramGatewayCommands


@pytest.fixture
def session(mocker) -> MagicMock:
    mock = mocker.AsyncMock()
    mock.execute.return_value = MagicMock()
    return mock


@pytest.fixture
def binding() -> ExternalChatBinding:
    return ExternalChatBinding(
        id=1,
        account_id=1,
        user_id=None,
        workspace_id=42,
        external_peer_id="12345",
        external_peer_kind="direct",
    )


@pytest.fixture
def adapter(mocker) -> MagicMock:
    mock = MagicMock()
    mock.send_message = AsyncMock()
    return mock


@pytest.fixture
def commands() -> TelegramGatewayCommands:
    return TelegramGatewayCommands()


@pytest.fixture(autouse=True)
def mock_auth(mocker):
    mocker.patch(
        "app.gateway.telegram.commands._load_user",
        new=AsyncMock(return_value=MagicMock()),
    )
    return mocker.patch(
        "app.gateway.telegram.commands.check_permission", new=AsyncMock()
    )


def _event(text: str) -> ParsedInboundEvent:
    return ParsedInboundEvent(
        platform="telegram",
        event_kind="message",
        external_peer_id="12345",
        external_peer_kind="direct",
        external_message_id=None,
        external_user_id="111",
        text=text,
        raw_payload={},
    )


def _run_mock(automation_id: int = 5) -> MagicMock:
    run = MagicMock()
    run.id = 123
    run.automation_id = automation_id
    run.status = RunStatus.SUCCEEDED
    run.finished_at = datetime.now(UTC)
    return run


def _automation_mock(name: str = "Test Automation") -> MagicMock:
    automation = MagicMock()
    automation.id = 5
    automation.name = name
    automation.workspace_id = 42
    automation.status = AutomationStatus.ACTIVE
    return automation


def _set_execute_first(session: MagicMock, value) -> None:
    session.execute.return_value.scalars.return_value.first.return_value = value


def _set_execute_all(session: MagicMock, values) -> None:
    session.execute.return_value.scalars.return_value.all.return_value = values


@pytest.mark.asyncio
async def test_status_command_no_recent_runs(session, adapter, binding, commands):
    _set_execute_first(session, None)
    event = _event("/status")

    await commands.handle_status_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    assert "No recent runs" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_status_command_shows_latest_run(session, adapter, binding, commands):
    run = _run_mock()
    automation = _automation_mock()
    _set_execute_first(session, run)
    session.get.return_value = automation
    event = _event("/status")

    await commands.handle_status_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    text = adapter.send_message.call_args.kwargs["text"]
    assert "Test Automation" in text
    assert "succeeded" in text


@pytest.mark.asyncio
async def test_status_command_orphan_run(session, adapter, binding, commands):
    run = _run_mock()
    _set_execute_first(session, run)
    session.get.return_value = None
    event = _event("/status")

    await commands.handle_status_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    text = adapter.send_message.call_args.kwargs["text"]
    assert "automation record is missing" in text
    assert "No recent runs" not in text


@pytest.mark.asyncio
async def test_status_command_permission_denied(
    session, adapter, binding, commands, mocker
):
    mocker.patch(
        "app.gateway.telegram.commands.check_permission",
        new=AsyncMock(side_effect=HTTPException(status_code=403)),
    )
    event = _event("/status")

    await commands.handle_status_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_status_command_user_not_found(
    session, adapter, binding, commands, mocker
):
    mocker.patch(
        "app.gateway.telegram.commands._load_user",
        new=AsyncMock(return_value=None),
    )
    event = _event("/status")

    await commands.handle_status_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_run_command_lists_active_automations(
    session, adapter, binding, commands
):
    event = _event("/run")
    auto_a = _automation_mock("Automation A")
    auto_b = _automation_mock("Automation B")
    _set_execute_all(session, [auto_a, auto_b])

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    text = adapter.send_message.call_args.kwargs["text"]
    assert "Automation A" in text
    assert "Automation B" in text
    assert "/run <name>" in text


@pytest.mark.asyncio
async def test_run_command_not_found(session, adapter, binding, commands):
    event = _event("/run Missing")
    _set_execute_first(session, None)

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    assert "Missing' not found" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_run_command_triggers_automation(
    session, adapter, binding, commands, mocker
):
    event = _event("/run Test Automation")
    automation = _automation_mock("Test Automation")
    _set_execute_first(session, automation)
    launch = mocker.patch("app.gateway.telegram.commands.launch_run", new=AsyncMock())

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    launch.assert_awaited_once()
    trigger = launch.call_args.kwargs["trigger"]
    assert trigger.automation_id == 5
    assert trigger.type == TriggerType.MANUAL
    assert launch.call_args.kwargs["runtime_inputs"] == {"fired_by": "telegram"}
    adapter.send_message.assert_awaited_once()
    assert "Run started" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_run_command_permission_denied(
    session, adapter, binding, commands, mocker
):
    event = _event("/run Test Automation")
    mocker.patch(
        "app.gateway.telegram.commands.check_permission",
        new=AsyncMock(side_effect=HTTPException(status_code=403)),
    )

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_run_command_user_not_found(session, adapter, binding, commands, mocker):
    mocker.patch(
        "app.gateway.telegram.commands._load_user",
        new=AsyncMock(return_value=None),
    )
    event = _event("/run Test Automation")

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_run_command_list_permission_before_query(
    session, adapter, binding, commands, mocker
):
    event = _event("/run")
    list_mock = mocker.patch(
        "app.gateway.telegram.commands._active_automations_for_workspace",
        new=AsyncMock(),
    )
    mocker.patch(
        "app.gateway.telegram.commands.check_permission",
        new=AsyncMock(side_effect=HTTPException(status_code=403)),
    )

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    list_mock.assert_not_awaited()
    adapter.send_message.assert_awaited_once()
    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_run_command_named_permission_before_lookup(
    session, adapter, binding, commands, mocker
):
    event = _event("/run Test Automation")
    find_mock = mocker.patch(
        "app.gateway.telegram.commands._find_active_automation_by_name",
        new=AsyncMock(),
    )
    mocker.patch(
        "app.gateway.telegram.commands.check_permission",
        new=AsyncMock(side_effect=HTTPException(status_code=403)),
    )

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    find_mock.assert_not_awaited()
    adapter.send_message.assert_awaited_once()
    assert "Access denied" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_run_command_long_automation_list(
    session, adapter, binding, commands, mocker
):
    event = _event("/run")
    long_names = [MagicMock(name=f"auto_{i}") for i in range(300)]
    for i, auto in enumerate(long_names):
        auto.name = f"Automation {i} {'x' * 50}"
    mocker.patch(
        "app.gateway.telegram.commands._active_automations_for_workspace",
        new=AsyncMock(return_value=long_names),
    )

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    text = adapter.send_message.call_args.kwargs["text"]
    assert len(text) <= 4096
    assert "truncated" in text


@pytest.mark.asyncio
async def test_run_command_bot_mention_strip(
    session, adapter, binding, commands, mocker
):
    event = _event("/run @NowingBot   Automation Name")
    automation = _automation_mock("Automation Name")
    find_mock = mocker.patch(
        "app.gateway.telegram.commands._find_active_automation_by_name",
        new=AsyncMock(return_value=automation),
    )
    mocker.patch("app.gateway.telegram.commands.launch_run", new=AsyncMock())

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    find_mock.assert_awaited_once_with(session, 42, "Automation Name")


@pytest.mark.asyncio
async def test_run_command_launch_run_dispatch_error(
    session, adapter, binding, commands, mocker
):
    event = _event("/run Test Automation")
    automation = _automation_mock("Test Automation")
    _set_execute_first(session, automation)
    mocker.patch(
        "app.gateway.telegram.commands.launch_run",
        new=AsyncMock(side_effect=DispatchError("bad inputs")),
    )

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    text = adapter.send_message.call_args.kwargs["text"]
    assert "Could not start run" in text
    assert "bad inputs" not in text


@pytest.mark.asyncio
async def test_run_command_launch_run_unexpected_error(
    session, adapter, binding, commands, mocker
):
    event = _event("/run Test Automation")
    automation = _automation_mock("Test Automation")
    _set_execute_first(session, automation)
    mocker.patch(
        "app.gateway.telegram.commands.launch_run",
        new=AsyncMock(side_effect=RuntimeError("explosion")),
    )

    await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.send_message.assert_awaited_once()
    text = adapter.send_message.call_args.kwargs["text"]
    assert "Could not start run" in text
    assert "explosion" not in text


@pytest.mark.asyncio
async def test_run_command_confirmation_send_failure(
    session, adapter, binding, commands, mocker
):
    event = _event("/run Test Automation")
    automation = _automation_mock("Test Automation")
    _set_execute_first(session, automation)
    mocker.patch("app.gateway.telegram.commands.launch_run", new=AsyncMock())
    adapter.send_message.side_effect = RuntimeError("send failed")

    result = await commands.handle_run_command(
        session=session, adapter=adapter, event=event, binding=binding
    )

    assert result is True
    adapter.send_message.assert_awaited_once()
