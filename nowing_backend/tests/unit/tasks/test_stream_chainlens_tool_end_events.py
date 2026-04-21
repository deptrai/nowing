"""Unit tests for Story 7.3 — chainlens_deep_research on_tool_end, custom events, regression, defensive."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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


def _assert_no_vendor_in_thinking(chunks: list[str]) -> None:
    """Assert 'chainlens' not visible in any thinking step title or items."""
    for step in _thinking_step_data(chunks):
        title = step.get("title", "")
        assert "chainlens" not in title.lower(), f"Vendor name in title: {title!r}"
        for item in step.get("items", []):
            assert "chainlens" not in item.lower(), f"Vendor name in item: {item!r}"


@pytest.fixture
def ss() -> VercelStreamingService:
    """Per-test VercelStreamingService instance."""
    return VercelStreamingService()


@pytest.fixture
def result() -> StreamResult:
    """Per-test StreamResult accumulator."""
    return StreamResult()


# ---------------------------------------------------------------------------
# on_tool_end — success path (sources > 0)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_end_chainlens_success_shows_sources_count(ss, result):
    """AC#4: on_tool_end success → thinking step completed with 'Sources found: N'."""
    tool_output = {
        "status": "success",
        "provider": "chainlens",
        "message": "Research done",
        "sources": [{"url": "https://a.com"}, {"url": "https://b.com"}],
    }
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"input": {"query": "DeFi"}},
            "metadata": {},
        },
        {
            "event": "on_tool_end",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"output": MagicMock(content=json.dumps(tool_output))},
            "metadata": {},
        },
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Sources found: 2" in combined
    assert "Deep researching" in combined


# ---------------------------------------------------------------------------
# on_tool_end — fallback path (service unavailable OR timeout)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fallback_origin,message",
    [
        ("unavailable", "Use generate_report..."),
        ("timeout", "Use generate_report..."),
    ],
    ids=["unavailable", "timeout"],
)
async def test_tool_end_chainlens_fallback_shows_research_completed(
    ss, result, fallback_origin, message
):
    """AC#5 + AC#6 + FR25: fallback (unavailable or timeout) → title stays 'Deep researching',
    item 'Research completed', no vendor/fallback strings emitted to SSE stream."""
    tool_output = {
        "status": "fallback",
        "provider": "nowing",
        "message": message,
    }
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"input": {"query": "test"}},
            "metadata": {},
        },
        {
            "event": "on_tool_end",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"output": MagicMock(content=json.dumps(tool_output))},
            "metadata": {},
        },
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Deep researching" in combined
    assert "Research completed" in combined
    _assert_no_vendor_in_thinking(chunks)
    for step in _thinking_step_data(chunks):
        assert "fallback" not in step.get("title", "").lower()
        for item in step.get("items", []):
            assert "fallback" not in item.lower()


@pytest.mark.asyncio
async def test_tool_end_chainlens_zero_sources_shows_research_completed(ss, result):
    """Success with 0 sources → 'Research completed', not 'Sources found: 0'."""
    tool_output = {
        "status": "success",
        "provider": "chainlens",
        "message": "Done",
        "sources": [],
    }
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"input": {"query": "test"}},
            "metadata": {},
        },
        {
            "event": "on_tool_end",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"output": MagicMock(content=json.dumps(tool_output))},
            "metadata": {},
        },
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Research completed" in combined
    assert "Sources found: 0" not in combined


# ---------------------------------------------------------------------------
# on_custom_event — research_status forwarding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_event_research_status_forwarded(ss, result):
    """AC#3: on_custom_event 'research_status' → format_data('research-status', payload) called."""
    status_payload = {"phase": "researching", "message": "Researching..."}
    events = [
        {
            "event": "on_custom_event",
            "name": "research_status",
            "run_id": "run-1",
            "data": status_payload,
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    with patch.object(ss, "format_data", wraps=ss.format_data) as spy:
        chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        spy.assert_called_once_with("research-status", status_payload)


@pytest.mark.asyncio
async def test_custom_event_research_status_no_vendor_name_in_output(ss, result):
    """AC#3 + FR25: forwarded event must not contain 'chainlens' in the SSE output."""
    status_payload = {"phase": "researching", "message": "Researching..."}
    events = [
        {
            "event": "on_custom_event",
            "name": "research_status",
            "run_id": "run-1",
            "data": status_payload,
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    _assert_no_vendor_in_thinking(chunks)


@pytest.mark.asyncio
async def test_custom_event_switching_phase_forwarded(ss, result):
    """Switching event (fallback branch) is forwarded with phase='switching'."""
    status_payload = {"phase": "switching", "message": "Researching..."}
    events = [
        {
            "event": "on_custom_event",
            "name": "research_status",
            "run_id": "run-1",
            "data": status_payload,
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "switching" in combined


# ---------------------------------------------------------------------------
# Regression: non-chainlens tools are not affected (AC#8)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_chainlens_tool_not_affected(ss, result):
    """Regression AC#8: generate_report tool_start still works, not mistaken as chainlens."""
    events = [
        {
            "event": "on_tool_start",
            "name": "generate_report",
            "run_id": "run-1",
            "data": {
                "input": {
                    "topic": "DeFi summary",
                    "report_style": "summary",
                    "source_strategy": "auto",
                }
            },
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Generating report" in combined or "Revising report" in combined
    assert "Deep researching" not in combined


@pytest.mark.asyncio
async def test_other_custom_event_not_forwarded_as_research_status(ss, result):
    """Other on_custom_event names are NOT forwarded as research-status."""
    events = [
        {
            "event": "on_custom_event",
            "name": "document_created",
            "run_id": "run-1",
            "data": {"some": "data"},
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    with patch.object(ss, "format_data", wraps=ss.format_data) as spy:
        await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        for call in spy.call_args_list:
            assert call[0][0] != "research-status"


# ---------------------------------------------------------------------------
# Defensive / boundary tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_end_chainlens_malformed_outputs_default_to_research_completed():
    """Defensive: tool_output as None/list/missing-sources/non-list-sources → safe fallback item."""
    for bad_output in [None, [], "not a dict", {"sources": None}, {"sources": "not a list"}, {}]:
        events = [
            {
                "event": "on_tool_start",
                "name": "chainlens_deep_research",
                "run_id": "run-bad",
                "data": {"input": {"query": "x"}},
                "metadata": {},
            },
            {
                "event": "on_tool_end",
                "name": "chainlens_deep_research",
                "run_id": "run-bad",
                "data": {"output": bad_output},
                "metadata": {},
            },
        ]
        agent = _make_agent(events)
        ss = VercelStreamingService()
        result = StreamResult()

        chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        combined = "".join(chunks)

        assert "Research completed" in combined, (
            f"Malformed output {bad_output!r} should render 'Research completed' fallback"
        )


@pytest.mark.asyncio
async def test_research_status_payload_none_does_not_crash(ss, result):
    """Defensive: on_custom_event with data=None must not propagate null to format_data."""
    events = [
        {
            "event": "on_custom_event",
            "name": "research_status",
            "run_id": "run-x",
            "data": None,
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    with patch.object(ss, "format_data", wraps=ss.format_data) as spy:
        await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        called_with_dict = any(
            call[0][0] == "research-status" and isinstance(call[0][1], dict)
            for call in spy.call_args_list
        )
        assert called_with_dict, "research-status must be forwarded with a dict payload"


@pytest.mark.asyncio
async def test_research_status_strips_vendor_and_fallback_strings(ss, result):
    """FR25 defense-in-depth: any field containing 'chainlens' or 'fallback' is dropped before forward."""
    events = [
        {
            "event": "on_custom_event",
            "name": "research_status",
            "run_id": "run-y",
            "data": {
                "phase": "searching",
                "message": "Calling Chainlens upstream",
                "provider": "chainlens",
                "note": "fallback path",
                "safe_field": "ok",
            },
            "metadata": {},
        }
    ]
    agent = _make_agent(events)

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "chainlens" not in combined.lower(), "Vendor name leaked to research-status SSE"
    assert "fallback" not in combined.lower(), "Fallback hint leaked to research-status SSE"
    assert "safe_field" in combined, "Non-banned field should be preserved"
    assert "ok" in combined
