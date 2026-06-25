"""Unit tests for Story 7.3 — chainlens_deep_research on_tool_start events."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.tasks.chat.stream_new_chat import _stream_agent_events, StreamResult
from app.services.new_streaming_service import VercelStreamingService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(events: list[dict]):
    """Return a mock agent whose astream_events yields the given events."""
    agent = MagicMock()

    async def _astream_events(input_data, version, config=None):
        for ev in events:
            yield ev

    agent.astream_events = _astream_events

    mock_state = MagicMock()
    mock_state.tasks = []
    agent.aget_state = AsyncMock(return_value=mock_state)

    return agent


async def _collect(gen) -> list[str]:
    """Drain an async generator into a list."""
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks


def _thinking_step_data(chunks: list[str]) -> list[dict]:
    """Extract parsed data-thinking-step payloads from SSE chunks."""
    steps = []
    for chunk in chunks:
        if "data-thinking-step" not in chunk:
            continue
        try:
            raw = chunk.strip()
            if raw.startswith("data: "):
                raw = raw[6:]
            payload = json.loads(raw)
            steps.append(payload.get("data", {}))
        except Exception:
            pass
    return steps


@pytest.fixture
def ss() -> VercelStreamingService:
    """Per-test VercelStreamingService instance."""
    return VercelStreamingService()


@pytest.fixture
def result() -> StreamResult:
    """Per-test StreamResult accumulator."""
    return StreamResult()


# ---------------------------------------------------------------------------
# on_tool_start — chainlens_deep_research
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_start_chainlens_emits_deep_researching_step(ss, result):
    """AC#2: on_tool_start for chainlens_deep_research emits a 'Deep researching' thinking step."""
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"input": {"query": "AI agents 2026", "sources": ["web"]}},
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(
        _stream_agent_events(agent, {}, {}, ss, result)
    )

    thinking_titles = []
    thinking_items_all = []
    for chunk in chunks:
        if "data-thinking-step" not in chunk:
            continue
        try:
            payload = json.loads(chunk.replace("data: ", "", 1))
            step_data = payload.get("data", {})
            thinking_titles.append(step_data.get("title", ""))
            thinking_items_all.extend(step_data.get("items", []))
        except Exception:
            pass

    assert any("Deep researching" in t for t in thinking_titles)
    assert any("AI agents 2026" in item for item in thinking_items_all)
    # FR25: no vendor name in thinking step
    for t in thinking_titles:
        assert "chainlens" not in t.lower()
    for item in thinking_items_all:
        assert "chainlens" not in item.lower()


@pytest.mark.asyncio
async def test_tool_start_chainlens_long_query_is_truncated(ss, result):
    """Query longer than 80 chars is truncated with ellipsis in thinking step."""
    long_query = "A" * 90
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"input": {"query": long_query}},
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    steps = _thinking_step_data(chunks)
    all_items = [item for step in steps for item in step.get("items", [])]

    assert any("A" * 80 in item for item in all_items)
    assert any("…" in item for item in all_items)
    assert not any("A" * 81 in item for item in all_items)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query_value",
    ["", None],
    ids=["empty_string", "none"],
)
async def test_tool_start_chainlens_blank_query_no_query_item(ss, result, query_value):
    """Empty or None query → 'Deep researching' title present but no 'Query:' item (graceful)."""
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"input": {"query": query_value}},
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Deep researching" in combined
    assert "Query:" not in combined


@pytest.mark.asyncio
async def test_tool_start_chainlens_query_exactly_80_chars_no_ellipsis(ss, result):
    """Boundary AC#2: query of exactly 80 chars must NOT be truncated/ellipsized."""
    q = "B" * 80
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-80",
            "data": {"input": {"query": q}},
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert q in combined, "Exact-80-char query should appear unmodified"
    assert "…" not in combined, "Should NOT add ellipsis at exactly 80 chars"
