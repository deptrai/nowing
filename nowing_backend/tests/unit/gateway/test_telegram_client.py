from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from telegram.error import BadRequest, RetryAfter

from app.gateway.base.adapter import PlatformSendResult
from app.gateway.telegram.client import TelegramClient
from app.gateway.telegram.formatting import unescape_markdown_v2


@pytest.fixture
def client(mocker):
    token = "test-token"
    client = TelegramClient(token)
    client.bot = mocker.AsyncMock()
    return client


@pytest.mark.asyncio
async def test_send_message_passes_reply_markup(client, mocker):
    from telegram import InlineKeyboardMarkup

    sent_msg = MagicMock()
    sent_msg.message_id = 42
    sent_msg.to_dict.return_value = {"message_id": 42}
    client.bot.send_message = mocker.AsyncMock(return_value=sent_msg)

    reply_markup = {
        "inline_keyboard": [[{"text": "View", "callback_data": "view_run:123"}]]
    }
    result = await client.send_message(
        chat_id="12345",
        text="Hello",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

    assert isinstance(result, PlatformSendResult)
    assert result.external_message_id == "42"
    call_kwargs = client.bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == "12345"
    assert call_kwargs["text"] == "Hello"
    assert call_kwargs["parse_mode"] == "Markdown"
    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_send_message_drops_invalid_reply_markup(client, mocker):
    sent_msg = MagicMock()
    sent_msg.message_id = 7
    sent_msg.to_dict.return_value = {"message_id": 7}
    client.bot.send_message = mocker.AsyncMock(return_value=sent_msg)

    result = await client.send_message(
        chat_id="12345",
        text="Hello",
        reply_markup={"not_a_keyboard": []},
    )

    assert result.external_message_id == "7"
    call_kwargs = client.bot.send_message.call_args.kwargs
    assert "reply_markup" not in call_kwargs


@pytest.mark.asyncio
async def test_send_message_falls_back_on_bad_markdown(client, mocker):
    sent_msg = MagicMock()
    sent_msg.message_id = 9
    sent_msg.to_dict.return_value = {"message_id": 9}
    client.bot.send_message = mocker.AsyncMock(
        side_effect=[
            BadRequest("Can't parse message text: can't find end of bold entity"),
            sent_msg,
        ]
    )

    result = await client.send_message(
        chat_id="12345",
        text="*unclosed bold",
        parse_mode="Markdown",
    )

    assert client.bot.send_message.call_count == 2
    assert client.bot.send_message.call_args.kwargs.get("parse_mode") is None
    assert result.external_message_id == "9"


@pytest.mark.asyncio
async def test_send_message_falls_back_on_bad_reply_markup(client, mocker):
    sent_msg = MagicMock()
    sent_msg.message_id = 11
    sent_msg.to_dict.return_value = {"message_id": 11}
    client.bot.send_message = mocker.AsyncMock(
        side_effect=[
            BadRequest("button_data_invalid"),
            sent_msg,
        ]
    )

    result = await client.send_message(
        chat_id="12345",
        text="Hello",
        reply_markup={
            "inline_keyboard": [
                [{"text": "Bad", "callback_data": "bad:data:way:too:long"}]
            ]
        },
    )

    assert client.bot.send_message.call_count == 2
    assert client.bot.send_message.call_args.kwargs.get("reply_markup") is None
    assert result.external_message_id == "11"


@pytest.mark.asyncio
async def test_send_message_retries_after_rate_limit(client, mocker):
    sent_msg = MagicMock()
    sent_msg.message_id = 13
    sent_msg.to_dict.return_value = {"message_id": 13}
    client.bot.send_message = mocker.AsyncMock(
        side_effect=[
            RetryAfter(1),
            sent_msg,
        ]
    )

    result = await client.send_message(chat_id="12345", text="Hello")

    assert client.bot.send_message.call_count == 2
    assert result.external_message_id == "13"


@pytest.mark.asyncio
async def test_answer_callback_query(client, mocker):
    client.bot.answer_callback_query = mocker.AsyncMock()

    await client.answer_callback_query(
        callback_query_id="cqid",
        text="Done",
        show_alert=True,
    )

    client.bot.answer_callback_query.assert_awaited_once_with(
        callback_query_id="cqid",
        text="Done",
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_edit_message_reply_markup(client, mocker):
    from telegram import InlineKeyboardMarkup

    client.bot.edit_message_reply_markup = mocker.AsyncMock()

    await client.edit_message_reply_markup(
        chat_id="12345",
        message_id="99",
        reply_markup={
            "inline_keyboard": [[{"text": "View", "callback_data": "view_run:123"}]]
        },
    )

    call_kwargs = client.bot.edit_message_reply_markup.call_args.kwargs
    assert call_kwargs["chat_id"] == "12345"
    assert call_kwargs["message_id"] == 99
    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_send_message_passes_url_button(client, mocker):
    from telegram import InlineKeyboardMarkup

    sent_msg = MagicMock()
    sent_msg.message_id = 21
    sent_msg.to_dict.return_value = {"message_id": 21}
    client.bot.send_message = mocker.AsyncMock(return_value=sent_msg)

    reply_markup = {
        "inline_keyboard": [[{"text": "Open", "url": "https://nowing.net"}]]
    }
    result = await client.send_message(
        chat_id="12345",
        text="Click below",
        reply_markup=reply_markup,
    )

    assert result.external_message_id == "21"
    call_kwargs = client.bot.send_message.call_args.kwargs
    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)
    assert call_kwargs["reply_markup"].inline_keyboard[0][0].url == "https://nowing.net"


@pytest.mark.asyncio
async def test_edit_message_passes_reply_markup(client, mocker):
    from telegram import InlineKeyboardMarkup

    edited_msg = MagicMock()
    edited_msg.message_id = 55
    edited_msg.to_dict.return_value = {"message_id": 55}
    client.bot.edit_message_text = mocker.AsyncMock(return_value=edited_msg)

    markup = {"inline_keyboard": [[{"text": "Updated", "callback_data": "ok"}]]}
    result = await client.edit_message(
        chat_id="12345",
        message_id="99",
        text="Updated text",
        reply_markup=markup,
    )

    assert result.external_message_id == "55"
    call_kwargs = client.bot.edit_message_text.call_args.kwargs
    assert call_kwargs["chat_id"] == "12345"
    assert call_kwargs["message_id"] == 99
    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_edit_message_keeps_username_chat_id(client, mocker):
    edited_msg = MagicMock()
    edited_msg.message_id = 77
    edited_msg.to_dict.return_value = {"message_id": 77}
    client.bot.edit_message_text = mocker.AsyncMock(return_value=edited_msg)

    result = await client.edit_message(
        chat_id="@nowing_channel",
        message_id="42",
        text="Updated",
    )

    assert result.external_message_id == "77"
    call_kwargs = client.bot.edit_message_text.call_args.kwargs
    assert call_kwargs["chat_id"] == "@nowing_channel"


@pytest.mark.asyncio
async def test_send_message_rejects_non_numeric_reply_to(client):
    with pytest.raises(
        ValueError, match="reply_to_message_id must be a numeric string"
    ):
        await client.send_message(
            chat_id="12345", text="Hello", reply_to_message_id="abc"
        )


@pytest.mark.asyncio
async def test_edit_message_rejects_non_numeric_message_id(client):
    with pytest.raises(ValueError, match="message_id must be a numeric string"):
        await client.edit_message(chat_id="12345", message_id="abc", text="Updated")


@pytest.mark.asyncio
async def test_edit_message_inline_returns_ok(client, mocker):
    client.bot.edit_message_text = mocker.AsyncMock(return_value=True)

    result = await client.edit_message(
        inline_message_id="inline-1",
        text="Updated",
    )

    assert result.external_message_id == "inline-1"
    assert result.raw_response == {"ok": True}


@pytest.mark.asyncio
async def test_send_message_unescapes_markdown_v2_on_parse_error(client, mocker):
    sent_msg = MagicMock()
    sent_msg.message_id = 15
    sent_msg.to_dict.return_value = {"message_id": 15}
    client.bot.send_message = mocker.AsyncMock(
        side_effect=[
            BadRequest("Can't parse message text: can't find end of bold entity"),
            sent_msg,
        ]
    )

    text = r"*hello \*world"
    await client.send_message(
        chat_id="12345",
        text=text,
        parse_mode="MarkdownV2",
    )

    assert client.bot.send_message.call_count == 2
    fallback_call = client.bot.send_message.call_args.kwargs
    assert fallback_call.get("parse_mode") is None
    assert fallback_call["text"] == unescape_markdown_v2(text)


@pytest.mark.asyncio
async def test_send_message_does_not_unescape_markdown_on_parse_error(client, mocker):
    sent_msg = MagicMock()
    sent_msg.message_id = 17
    sent_msg.to_dict.return_value = {"message_id": 17}
    client.bot.send_message = mocker.AsyncMock(
        side_effect=[
            BadRequest("Can't parse message text: can't find end of bold entity"),
            sent_msg,
        ]
    )

    text = "*unclosed bold"
    await client.send_message(
        chat_id="12345",
        text=text,
        parse_mode="Markdown",
    )

    fallback_call = client.bot.send_message.call_args.kwargs
    assert fallback_call.get("parse_mode") is None
    assert fallback_call["text"] == text
