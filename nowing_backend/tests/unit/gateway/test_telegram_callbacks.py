"""Tests for Telegram callback query dispatch."""

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
from app.gateway.telegram.callbacks import handle_callback_query


@pytest.fixture
def session(mocker) -> MagicMock:
    return mocker.AsyncMock()


@pytest.fixture
def binding() -> ExternalChatBinding:
    # user_id=None avoids loading a User in these unit tests.
    return ExternalChatBinding(
        id=1,
        account_id=1,
        user_id=None,
        workspace_id=42,
        external_peer_id="12345",
        external_peer_kind="direct",
    )


def _event(text: str = "view_run:123") -> ParsedInboundEvent:
    return ParsedInboundEvent(
        platform="telegram",
        event_kind="callback_query",
        external_peer_id="12345",
        external_peer_kind="direct",
        external_message_id="99",
        external_user_id="111",
        text=text,
        metadata={"callback_query_id": "cqid"},
        raw_payload={},
    )


@pytest.fixture
def event() -> ParsedInboundEvent:
    return _event()


@pytest.fixture
def adapter(mocker) -> MagicMock:
    mock = MagicMock()
    mock.send_message = AsyncMock()
    mock.edit_message = AsyncMock()
    mock.answer_callback_query = AsyncMock()
    return mock


@pytest.fixture(autouse=True)
def mock_auth(mocker):
    mocker.patch(
        "app.gateway.telegram.callbacks._load_user",
        new=AsyncMock(return_value=MagicMock()),
    )
    return mocker.patch(
        "app.gateway.telegram.callbacks.check_permission", new=AsyncMock()
    )


@pytest.mark.asyncio
async def test_view_run_edits_message(session, adapter, binding, event):
    run = MagicMock()
    run.id = 123
    run.status = RunStatus.SUCCEEDED
    run.finished_at = datetime.now(UTC)
    run.automation_id = 5

    automation = MagicMock()
    automation.id = 5
    automation.name = "Test Automation"
    automation.workspace_id = 42

    session.get.side_effect = [run, automation]

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    adapter.edit_message.assert_awaited_once()
    call = adapter.edit_message.call_args.kwargs
    assert "Test Automation" in call["text"]
    assert call["external_peer_id"] == "12345"
    assert call["external_message_id"] == "99"


@pytest.mark.asyncio
async def test_view_run_not_found(session, adapter, binding):
    session.get.return_value = None
    event = _event("view_run:999")

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    adapter.send_message.assert_awaited_once()
    assert "not found" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_view_run_permission_denied(session, adapter, binding, mocker):
    event = _event("view_run:123")
    mocker.patch(
        "app.gateway.telegram.callbacks.check_permission",
        new=AsyncMock(side_effect=HTTPException(status_code=403)),
    )

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    assert "Access denied" in adapter.answer_callback_query.call_args.kwargs["text"]
    session.get.assert_not_called()
    adapter.edit_message.assert_not_awaited()
    adapter.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_view_run_user_not_found(session, adapter, binding, mocker):
    event = _event("view_run:123")
    mocker.patch(
        "app.gateway.telegram.callbacks._load_user",
        new=AsyncMock(return_value=None),
    )

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    assert "Access denied" in adapter.answer_callback_query.call_args.kwargs["text"]
    session.get.assert_not_called()
    adapter.edit_message.assert_not_awaited()
    adapter.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_rerun_triggers_automation(session, adapter, binding, mocker):
    event = _event("rerun:5")
    automation = MagicMock()
    automation.id = 5
    automation.name = "Test Automation"
    automation.workspace_id = 42
    automation.status = AutomationStatus.ACTIVE

    session.get.return_value = automation
    launch = mocker.patch("app.gateway.telegram.callbacks.launch_run", new=AsyncMock())

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    launch.assert_awaited_once()
    launch_call = launch.call_args.kwargs
    assert launch_call["trigger"].automation_id == 5
    assert launch_call["trigger"].type == TriggerType.MANUAL
    adapter.answer_callback_query.assert_awaited_once()
    adapter.send_message.assert_awaited_once()
    assert "Started run" in adapter.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_rerun_not_active(session, adapter, binding):
    event = _event("rerun:5")
    automation = MagicMock()
    automation.id = 5
    automation.status = AutomationStatus.PAUSED

    session.get.return_value = automation

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    assert "paused" in adapter.answer_callback_query.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_rerun_permission_denied(session, adapter, binding, mocker):
    event = _event("rerun:5")
    mocker.patch(
        "app.gateway.telegram.callbacks.check_permission",
        new=AsyncMock(side_effect=HTTPException(status_code=403)),
    )

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    assert "Access denied" in adapter.answer_callback_query.call_args.kwargs["text"]
    session.get.assert_not_called()
    adapter.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_rerun_launch_run_dispatch_error(session, adapter, binding, mocker):
    event = _event("rerun:5")
    automation = MagicMock()
    automation.id = 5
    automation.name = "Test Automation"
    automation.workspace_id = 42
    automation.status = AutomationStatus.ACTIVE

    session.get.return_value = automation
    mocker.patch(
        "app.gateway.telegram.callbacks.launch_run",
        new=AsyncMock(side_effect=DispatchError("bad inputs")),
    )

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    text = adapter.answer_callback_query.call_args.kwargs["text"]
    assert "Could not start run" in text
    assert "bad inputs" not in text
    adapter.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_rerun_launch_run_unexpected_error(session, adapter, binding, mocker):
    event = _event("rerun:5")
    automation = MagicMock()
    automation.id = 5
    automation.name = "Test Automation"
    automation.workspace_id = 42
    automation.status = AutomationStatus.ACTIVE

    session.get.return_value = automation
    mocker.patch(
        "app.gateway.telegram.callbacks.launch_run",
        new=AsyncMock(side_effect=RuntimeError("explosion")),
    )

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once()
    text = adapter.answer_callback_query.call_args.kwargs["text"]
    assert "Could not start run" in text
    assert "explosion" not in text
    adapter.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_callback_data_answers_only(session, adapter, binding):
    event = _event("unknown:stuff")

    await handle_callback_query(
        session=session, adapter=adapter, event=event, binding=binding
    )

    adapter.answer_callback_query.assert_awaited_once_with(callback_query_id="cqid")
    adapter.send_message.assert_not_awaited()
    adapter.edit_message.assert_not_awaited()
