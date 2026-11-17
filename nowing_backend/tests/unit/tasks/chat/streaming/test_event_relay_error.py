"""Unit tests for EventRelay handling of on_tool_error events."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.tasks.chat.streaming.graph_stream.result import StreamingResult
from app.tasks.chat.streaming.relay.event_relay import EventRelay
from app.tasks.chat.streaming.relay.state import AgentEventRelayState


@pytest.mark.asyncio
async def test_event_relay_handles_on_tool_error_without_hanging():
    streaming_service = MagicMock()
    streaming_service.format_text_end.return_value = "TEXT_END"
    streaming_service.format_tool_input_start.return_value = "TOOL_INPUT_START"
    streaming_service.format_tool_input_end.return_value = "TOOL_INPUT_END"
    streaming_service.format_tool_call_completed.return_value = "TOOL_COMPLETED"
    streaming_service.format_thinking_step_complete.return_value = "THINKING_COMPLETE"
    streaming_service.format_thinking_step_create.return_value = "THINKING_CREATE"
    streaming_service.format_tool_call_start.return_value = "TOOL_START"

    relay = EventRelay(streaming_service=streaming_service)
    state = AgentEventRelayState()
    result = StreamingResult()
    content_builder = MagicMock()

    async def mock_events():
        # 1. Tool starts
        yield {
            "event": "on_tool_start",
            "name": "topcv_scrape",
            "run_id": "run-topcv-1",
            "data": {"input": {"keyword": "python"}},
            "tags": [],
            "metadata": {"langgraph_step": 1},
        }
        # 2. Tool encounters unhandled error
        yield {
            "event": "on_tool_error",
            "name": "topcv_scrape",
            "run_id": "run-topcv-1",
            "data": {"error": RuntimeError("Medirus connection refused")},
            "tags": [],
            "metadata": {"langgraph_step": 1},
        }

    frames = [
        f
        async for f in relay.relay(
            mock_events(),
            state=state,
            result=result,
            content_builder=content_builder,
        )
    ]

    assert len(frames) > 0
    # The tool run step should be completed, not left pending
    assert any("thinking" in s for s in state.completed_step_ids)
    # Active tool depth decremented back to 0
    assert state.active_tool_depth == 0
