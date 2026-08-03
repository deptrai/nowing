from __future__ import annotations

import pytest

from app.gateway.telegram.adapter import TelegramAdapter


@pytest.fixture
def adapter():
    return TelegramAdapter("test-token")


def test_parse_message(adapter):
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 42,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 987, "first_name": "Alice", "username": "alice"},
            "text": "/start CODE",
        },
    }

    parsed = adapter.parse_inbound(payload)

    assert parsed.platform == "telegram"
    assert parsed.event_kind == "message"
    assert parsed.external_peer_id == "12345"
    assert parsed.external_peer_kind == "direct"
    assert parsed.external_message_id == "42"
    assert parsed.external_user_id == "987"
    assert parsed.text == "/start CODE"
    assert parsed.display_name == "Alice"
    assert parsed.username == "alice"


def test_parse_callback_query(adapter):
    payload = {
        "update_id": 2,
        "callback_query": {
            "id": "cqid123",
            "from": {"id": 987, "first_name": "Alice", "username": "alice"},
            "message": {
                "message_id": 55,
                "chat": {"id": 12345, "type": "private"},
            },
            "data": "view_run:123",
        },
    }

    parsed = adapter.parse_inbound(payload)

    assert parsed.platform == "telegram"
    assert parsed.event_kind == "callback_query"
    assert parsed.external_peer_id == "12345"
    assert parsed.external_message_id == "55"
    assert parsed.external_user_id == "987"
    assert parsed.text == "view_run:123"
    assert parsed.metadata["callback_query_id"] == "cqid123"


def test_parse_callback_query_without_message(adapter):
    payload = {
        "update_id": 3,
        "callback_query": {
            "id": "cqid456",
            "from": {"id": 987},
            "inline_message_id": "inline-1",
            "data": "rerun:456",
        },
    }

    parsed = adapter.parse_inbound(payload)

    assert parsed.event_kind == "callback_query"
    assert parsed.external_peer_id == "inline:inline-1"
    assert parsed.external_message_id == "inline-1"
    assert parsed.external_user_id == "987"
    assert parsed.text == "rerun:456"
    assert parsed.metadata["inline_message_id"] == "inline-1"


@pytest.mark.asyncio
async def test_answer_callback_query(adapter, mocker):
    adapter.client.answer_callback_query = mocker.AsyncMock()

    await adapter.answer_callback_query(
        callback_query_id="cqid",
        text="Done",
        show_alert=True,
    )

    adapter.client.answer_callback_query.assert_awaited_once_with(
        callback_query_id="cqid",
        text="Done",
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_edit_message_reply_markup(adapter, mocker):
    adapter.client.edit_message_reply_markup = mocker.AsyncMock()
    markup = {"inline_keyboard": [[{"text": "View", "callback_data": "view:1"}]]}

    await adapter.edit_message_reply_markup(
        external_peer_id="12345",
        external_message_id="99",
        reply_markup=markup,
    )

    adapter.client.edit_message_reply_markup.assert_awaited_once_with(
        chat_id="12345",
        message_id="99",
        reply_markup=markup,
    )


def test_parse_unknown_update_defaults_to_other(adapter):
    payload = {"update_id": 4, "my_chat_member": {"chat": {"id": 12345}}}

    parsed = adapter.parse_inbound(payload)

    assert parsed.event_kind == "other"
    assert parsed.external_peer_id is None
    assert parsed.text is None
