"""Unit tests for chainlens_deep_research LangGraph tool (Story 7.2)."""
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.new_chat.tools.chainlens_research import (
    create_chainlens_research_tool,
)
from app.services.chainlens_research_service import ChainlensUnavailableError


@pytest.fixture
def tool():
    return create_chainlens_research_tool()


@pytest.mark.asyncio
async def test_success_path_returns_chainlens_result(tool):
    """AC#1 success branch: available=True + research() succeeds → status=success."""
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc, patch(
        "app.agents.new_chat.tools.chainlens_research.dispatch_custom_event"
    ):
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(
            return_value={
                "message": "Research result about AI",
                "sources": [{"url": "https://example.com"}],
            }
        )

        result = await tool.ainvoke({"query": "AI agents 2026"})

        assert result["status"] == "success"
        assert result["provider"] == "chainlens"
        assert result["message"] == "Research result about AI"
        assert len(result["sources"]) == 1
        mock_svc.research.assert_awaited_once_with("AI agents 2026", None)


@pytest.mark.asyncio
async def test_success_path_passes_sources_correctly(tool):
    """AC#1 + task 4.6: sources param forwarded to research()."""
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc, patch(
        "app.agents.new_chat.tools.chainlens_research.dispatch_custom_event"
    ):
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(
            return_value={"message": "ok", "sources": []}
        )

        await tool.ainvoke({"query": "DeFi", "sources": ["web", "academic"]})

        mock_svc.research.assert_awaited_once_with("DeFi", ["web", "academic"])


@pytest.mark.asyncio
async def test_unavailable_returns_fallback_not_raise(tool):
    """AC#1 fallback branch: is_available()=False → fallback dict, no exception."""
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc, patch(
        "app.agents.new_chat.tools.chainlens_research.dispatch_custom_event"
    ):
        mock_svc.is_available = AsyncMock(return_value=False)

        result = await tool.ainvoke({"query": "test"})

        assert result["status"] == "fallback"
        assert result["provider"] == "nowing"
        assert "generate_report" in result["message"]
        # FR25: must NOT leak vendor name in fallback message
        assert "chainlens" not in result["message"].lower()
        # research() should NOT be called
        assert not hasattr(mock_svc, "research") or not mock_svc.research.called


@pytest.mark.asyncio
async def test_research_exception_returns_fallback_not_raise(tool):
    """AC#2: research() raises ChainlensUnavailableError → fallback, no exception."""
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc, patch(
        "app.agents.new_chat.tools.chainlens_research.dispatch_custom_event"
    ):
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(
            side_effect=ChainlensUnavailableError("HTTP 503: service unavailable")
        )

        # Must NOT raise — must return fallback dict
        result = await tool.ainvoke({"query": "blockchain trends"})

        assert result["status"] == "fallback"
        assert result["provider"] == "nowing"
        assert "generate_report" in result["message"]


@pytest.mark.asyncio
async def test_research_unexpected_exception_returns_fallback(tool):
    """AC#2: any unexpected exception → fallback dict, no exception propagated."""
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc, patch(
        "app.agents.new_chat.tools.chainlens_research.dispatch_custom_event"
    ):
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(side_effect=RuntimeError("unexpected"))

        result = await tool.ainvoke({"query": "test"})

        assert result["status"] == "fallback"
        assert result["provider"] == "nowing"


@pytest.mark.asyncio
async def test_event_dispatch_called_with_neutral_message(tool):
    """AC#3: dispatch_custom_event called with neutral message (no 'chainlens' in message)."""
    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc, patch(
        "app.agents.new_chat.tools.chainlens_research.dispatch_custom_event"
    ) as mock_dispatch:
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(return_value={"message": "ok", "sources": []})

        await tool.ainvoke({"query": "test"})

        # Must be called at least once
        assert mock_dispatch.called
        # All dispatched event messages must be neutral — no vendor name
        for call in mock_dispatch.call_args_list:
            event_data = call[0][1]  # second positional arg = data dict
            assert "chainlens" not in event_data.get("message", "").lower()
            assert "fallback" not in event_data.get("phase", "").lower() or \
                   "chainlens" not in event_data.get("message", "").lower()


@pytest.mark.asyncio
async def test_research_exception_logs_warning(tool, caplog):
    """AC#2: ChainlensUnavailableError → logs warning (not error)."""
    import logging

    with patch(
        "app.agents.new_chat.tools.chainlens_research.ChainlensResearchService"
    ) as mock_svc, patch(
        "app.agents.new_chat.tools.chainlens_research.dispatch_custom_event"
    ):
        mock_svc.is_available = AsyncMock(return_value=True)
        mock_svc.research = AsyncMock(
            side_effect=ChainlensUnavailableError("timeout")
        )

        with caplog.at_level(logging.WARNING, logger="app.agents.new_chat.tools.chainlens_research"):
            await tool.ainvoke({"query": "test"})

        assert any("chainlens research failed" in r.message for r in caplog.records)
        # Must NOT log at ERROR level
        assert not any(r.levelno >= logging.ERROR for r in caplog.records)
