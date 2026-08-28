"""Unit tests for background title generation with timeout and retry (td-5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.chat.streaming.flows.new_chat.title_gen import (
    _generate_title,
    spawn_title_task,
)


@pytest.mark.asyncio
async def test_spawn_title_task_returns_none_when_assistant_id_is_none():
    assert (
        spawn_title_task(
            chat_id=1,
            user_query="Hello",
            user_image_data_urls=None,
            assistant_message_id=None,
            llm=MagicMock(),
            agent_config=None,
        )
        is None
    )


@pytest.mark.asyncio
async def test_generate_title_not_first_response():
    with patch(
        "app.tasks.chat.streaming.flows.new_chat.title_gen.shielded_async_session"
    ) as mock_session_ctx:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Non-empty scalars means this is NOT the first response
        mock_result.scalars().first.return_value = 999
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__aenter__.return_value = mock_session

        title, usage = await _generate_title(
            chat_id=1,
            user_query="Hello",
            user_image_data_urls=None,
            assistant_message_id=1000,
            llm=MagicMock(),
            agent_config=None,
        )

        assert title is None
        assert usage is None


@pytest.mark.asyncio
async def test_generate_title_with_timeout_and_retry_success():
    with patch(
        "app.tasks.chat.streaming.flows.new_chat.title_gen.shielded_async_session"
    ) as mock_session_ctx:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # First response
        mock_result.scalars().first.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__aenter__.return_value = mock_session

        mock_choice = MagicMock()
        mock_choice.message.content = "BĐS Quận 1"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.model = "gpt-4o"

        llm = MagicMock()
        llm.model = "openai/gpt-4o"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            # First attempt fails with TimeoutError, second attempt succeeds
            mock_acompletion.side_effect = [TimeoutError("timed out"), mock_response]

            title, usage = await _generate_title(
                chat_id=1,
                user_query="Tìm nhà quận 1",
                user_image_data_urls=None,
                assistant_message_id=1000,
                llm=llm,
                agent_config=None,
            )

            assert title == "BĐS Quận 1"
            assert usage == {
                "model": "gpt-4o",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
            assert mock_acompletion.call_count == 2


@pytest.mark.asyncio
async def test_generate_title_all_retries_fail_gracefully():
    with patch(
        "app.tasks.chat.streaming.flows.new_chat.title_gen.shielded_async_session"
    ) as mock_session_ctx:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_ctx.return_value.__aenter__.return_value = mock_session

        llm = MagicMock()
        llm.model = "openai/gpt-4o"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.side_effect = TimeoutError("all timed out")

            title, usage = await _generate_title(
                chat_id=1,
                user_query="Tìm nhà quận 1",
                user_image_data_urls=None,
                assistant_message_id=1000,
                llm=llm,
                agent_config=None,
            )

            assert title is None
            assert usage is None
            assert mock_acompletion.call_count == 2
