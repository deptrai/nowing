"""Red-phase unit tests for Story 27.2b — generate_meeting_minutes chat tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.agents.chat.multi_agent_chat.main_agent.tools.meeting_minutes.generate_meeting_minutes import (
    create_generate_meeting_minutes_tool,
)


@pytest.fixture
def tool_factory():
    return lambda: create_generate_meeting_minutes_tool(
        {
            "workspace_id": 1,
            "user_id": UUID("00000000-0000-0000-0000-000000000001"),
        }
    )


@pytest.mark.unit
async def test_tool_returns_validation_failed_when_feature_flag_off(tool_factory):
    """AC-5: MEETING_MINUTES_ENABLED=false returns validation_failed."""
    with patch("app.config.config.MEETING_MINUTES_ENABLED", False):
        tool = tool_factory()
        result = await tool.ainvoke({"audio_url": "https://example.com/m.mp3"})
        assert result["status"] == "validation_failed"
        assert "not enabled" in result["error"].lower()


@pytest.mark.unit
async def test_tool_returns_validation_failed_when_both_inputs_missing(tool_factory):
    """AC-1/AC-6: missing audio_url and document_id returns validation_failed."""
    with patch("app.config.config.MEETING_MINUTES_ENABLED", True):
        tool = tool_factory()
        result = await tool.ainvoke({})
        assert result["status"] == "validation_failed"
        assert "Provide an audio file or URL" in result["error"]


@pytest.mark.unit
async def test_tool_creates_meeting_minutes_row_and_enqueues_worker(tool_factory):
    """AC-1: tool creates row and returns processing."""
    with patch("app.config.config.MEETING_MINUTES_ENABLED", True), patch(
        "app.agents.chat.multi_agent_chat.main_agent.tools.meeting_minutes.generate_meeting_minutes.MeetingMinutesService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        from app.services.meeting_minutes.schemas import GenerateMeetingMinutesOutput

        mock_service.create = AsyncMock(
            return_value=GenerateMeetingMinutesOutput(
                meeting_minutes_id=42,
                status="processing",
                download_url="/api/v1/meeting-minutes/42/download",
            )
        )
        tool = tool_factory()
        result = await tool.ainvoke({"audio_url": "https://example.com/m.mp3"})
        assert result["meeting_minutes_id"] == 42
        assert result["status"] == "processing"
        mock_service.create.assert_called_once()
