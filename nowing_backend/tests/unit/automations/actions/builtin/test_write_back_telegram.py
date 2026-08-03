"""Unit tests for the ``write_back_telegram`` action."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automations.actions.builtin.write_back_telegram.invoke import (
    _resolve_chat_id,
    _resolve_telegram_account,
    write_back_telegram,
)
from app.automations.actions.builtin.write_back_telegram.params import (
    TelegramActionParams,
)
from app.db import ExternalChatAccount, ExternalChatBindingState, ExternalChatPlatform

pytestmark = pytest.mark.unit


def _account(
    account_id: int = 1,
    *,
    is_system: bool = False,
    platform=ExternalChatPlatform.TELEGRAM,
    owner_workspace_id: int = 42,
    owner_user_id: uuid.UUID | None = None,
    suspended_at=None,
) -> MagicMock:
    account = MagicMock()
    account.id = account_id
    account.platform = platform
    account.is_system_account = is_system
    account.owner_workspace_id = owner_workspace_id
    account.owner_user_id = owner_user_id
    account.suspended_at = suspended_at
    account.encrypted_credentials = "encrypted"
    return account


def _binding(
    *, external_peer_id: str, state=ExternalChatBindingState.BOUND
) -> MagicMock:
    binding = MagicMock()
    binding.external_peer_id = external_peer_id
    binding.state = state
    binding.suspended_at = None
    binding.revoked_at = None
    return binding


def _make_session(get_result=None, execute_result=None):
    session = MagicMock()
    session.get = AsyncMock(return_value=get_result)
    if execute_result is not None:
        session.execute = AsyncMock(return_value=execute_result)
    return session


def _result_mock(first):
    scalars_mock = MagicMock(first=MagicMock(return_value=first))
    return MagicMock(scalars=MagicMock(return_value=scalars_mock))


@pytest.mark.asyncio
async def test_params_defaults():
    params = TelegramActionParams(text="hello")
    assert params.parse_mode == "Markdown"
    assert params.use_system_bot is True
    assert params.account_id is None
    assert params.connector_name is None
    assert params.object_id is None


@pytest.mark.asyncio
async def test_resolve_account_by_id():
    account = _account(account_id=5)
    session = _make_session(get_result=account)

    params = TelegramActionParams(
        chat_id="12345",
        text="Hello",
        account_id=5,
    )
    result = await _resolve_telegram_account(
        SimpleNamespace(session=session, workspace_id=42), params
    )

    assert result == account
    session.get.assert_awaited_once_with(ExternalChatAccount, 5)


@pytest.mark.asyncio
async def test_resolve_account_by_id_rejects_cross_workspace():
    account = _account(
        account_id=5,
        owner_workspace_id=99,
        owner_user_id=uuid.uuid4(),
    )
    session = _make_session(get_result=account)

    params = TelegramActionParams(
        text="Hello",
        account_id=5,
    )
    with pytest.raises(ValueError, match="does not belong"):
        await _resolve_telegram_account(
            SimpleNamespace(
                session=session, workspace_id=42, creator_user_id=uuid.uuid4()
            ),
            params,
        )


@pytest.mark.asyncio
async def test_resolve_account_by_id_rejects_suspended():
    account = _account(account_id=5, suspended_at="2026-08-01")
    session = _make_session(get_result=account)

    params = TelegramActionParams(text="Hello", account_id=5)
    with pytest.raises(ValueError, match="suspended"):
        await _resolve_telegram_account(
            SimpleNamespace(session=session, workspace_id=42), params
        )


@pytest.mark.asyncio
async def test_resolve_system_account():
    account = _account(account_id=1, is_system=True)
    session = _make_session(execute_result=_result_mock(account))

    params = TelegramActionParams(
        chat_id="12345",
        text="Hello",
        use_system_bot=True,
    )
    result = await _resolve_telegram_account(
        SimpleNamespace(session=session, workspace_id=42), params
    )

    assert result == account


@pytest.mark.asyncio
async def test_resolve_use_system_bot_false_without_account_id_fails():
    session = _make_session()
    params = TelegramActionParams(
        text="Hello",
        use_system_bot=False,
    )
    with pytest.raises(ValueError, match="Provide a Telegram account_id"):
        await _resolve_telegram_account(
            SimpleNamespace(session=session, workspace_id=42), params
        )


@pytest.mark.asyncio
async def test_resolve_chat_id_from_binding():
    account = _account(account_id=1)
    binding = _binding(external_peer_id="67890")
    session = _make_session(get_result=account, execute_result=_result_mock(binding))

    params = TelegramActionParams(text="Hello", account_id=1)
    chat_id = await _resolve_chat_id(
        SimpleNamespace(session=session, workspace_id=42, creator_user_id=uuid.uuid4()),
        account,
        params,
    )
    assert chat_id == "67890"


@pytest.mark.asyncio
async def test_resolve_chat_id_missing_binding():
    account = _account(account_id=1)
    session = _make_session(get_result=account, execute_result=_result_mock(None))

    params = TelegramActionParams(text="Hello", account_id=1)
    with pytest.raises(ValueError, match="No Telegram chat bound"):
        await _resolve_chat_id(
            SimpleNamespace(
                session=session,
                workspace_id=42,
                creator_user_id=uuid.uuid4(),
            ),
            account,
            params,
        )


@pytest.mark.asyncio
async def test_write_back_telegram_sends_message():
    account = _account(account_id=1)
    session = _make_session(get_result=account)

    params = TelegramActionParams(
        chat_id="12345",
        text="Hello from automation",
        account_id=1,
        parse_mode="Markdown",
        reply_markup={"inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]},
    )

    send_result = MagicMock()
    send_result.external_message_id = "99"

    with (
        patch(
            "app.automations.actions.builtin.write_back_telegram.invoke.account_token",
            return_value="token",
        ),
        patch(
            "app.automations.actions.builtin.write_back_telegram.invoke.TelegramAdapter"
        ) as adapter_cls,
    ):
        adapter = MagicMock()
        adapter.send_message = AsyncMock(return_value=send_result)
        adapter_cls.return_value = adapter

        result = await write_back_telegram(
            SimpleNamespace(session=session, workspace_id=42), params
        )

    assert result["provider"] == "telegram"
    assert result["account_id"] == 1
    assert result["chat_id"] == "12345"
    assert result["message_id"] == "99"
    assert result["parse_mode"] == "Markdown"
    assert result["reply_markup"] == {
        "inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]
    }

    call = adapter.send_message.call_args.kwargs
    assert call["external_peer_id"] == "12345"
    assert call["text"] == "Hello from automation"
    assert call["parse_mode"] == "Markdown"
    assert call["reply_markup"] == {
        "inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]
    }


@pytest.mark.asyncio
async def test_write_back_telegram_requires_token():
    account = _account(account_id=1)
    session = _make_session(get_result=account)

    params = TelegramActionParams(chat_id="12345", text="Hello", account_id=1)

    with (
        patch(
            "app.automations.actions.builtin.write_back_telegram.invoke.account_token",
            return_value=None,
        ),
        pytest.raises(ValueError, match="no usable token"),
    ):
        await write_back_telegram(
            SimpleNamespace(session=session, workspace_id=42), params
        )


@pytest.mark.asyncio
async def test_write_back_telegram_resolves_chat_id_from_binding():
    account = _account(account_id=1)
    binding = _binding(external_peer_id="67890")
    session = _make_session(get_result=account, execute_result=_result_mock(binding))

    creator_id = uuid.uuid4()
    params = TelegramActionParams(
        chat_id=None,
        text="Hello from binding",
        account_id=1,
    )

    send_result = MagicMock()
    send_result.external_message_id = "55"

    with (
        patch(
            "app.automations.actions.builtin.write_back_telegram.invoke.account_token",
            return_value="token",
        ),
        patch(
            "app.automations.actions.builtin.write_back_telegram.invoke.TelegramAdapter"
        ) as adapter_cls,
    ):
        adapter = MagicMock()
        adapter.send_message = AsyncMock(return_value=send_result)
        adapter_cls.return_value = adapter

        result = await write_back_telegram(
            SimpleNamespace(
                session=session, workspace_id=42, creator_user_id=creator_id
            ),
            params,
        )

    assert result["chat_id"] == "67890"
    call = adapter.send_message.call_args.kwargs
    assert call["external_peer_id"] == "67890"


@pytest.mark.asyncio
async def test_write_back_telegram_uses_system_bot():
    account = _account(account_id=1, is_system=True)
    session = _make_session(execute_result=_result_mock(account))

    params = TelegramActionParams(chat_id="12345", text="Hello")

    send_result = MagicMock()
    send_result.external_message_id = "77"

    with (
        patch(
            "app.automations.actions.builtin.write_back_telegram.invoke.account_token",
            return_value="token",
        ),
        patch(
            "app.automations.actions.builtin.write_back_telegram.invoke.TelegramAdapter"
        ) as adapter_cls,
    ):
        adapter = MagicMock()
        adapter.send_message = AsyncMock(return_value=send_result)
        adapter_cls.return_value = adapter

        result = await write_back_telegram(
            SimpleNamespace(session=session, workspace_id=42), params
        )

    assert result["account_id"] == 1
    call = adapter.send_message.call_args.kwargs
    assert call["external_peer_id"] == "12345"
