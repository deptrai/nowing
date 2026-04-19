"""Unit tests for Story 7.3 — chainlens_deep_research event handling in _stream_agent_events."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tasks.chat.stream_new_chat import _stream_agent_events, StreamResult
from app.services.new_streaming_service import VercelStreamingService


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

    # aget_state is awaited after the event loop — return a stub with no interrupts
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
    import json as _json
    steps = []
    for chunk in chunks:
        if "data-thinking-step" not in chunk:
            continue
        try:
            raw = chunk.strip()
            if raw.startswith("data: "):
                raw = raw[6:]
            payload = _json.loads(raw)
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


def _make_streaming_service() -> VercelStreamingService:
    return VercelStreamingService()


# ---------------------------------------------------------------------------
# on_tool_start — chainlens_deep_research
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_start_chainlens_emits_deep_researching_step():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(
        _stream_agent_events(agent, {}, {}, ss, result)
    )

    # Parse thinking step chunks only (data-thinking-step events)
    import json as _json
    thinking_titles = []
    thinking_items_all = []
    for chunk in chunks:
        if "data-thinking-step" not in chunk:
            continue
        try:
            payload = _json.loads(chunk.replace("data: ", "", 1))
            step_data = payload.get("data", {})
            thinking_titles.append(step_data.get("title", ""))
            thinking_items_all.extend(step_data.get("items", []))
        except Exception:
            pass

    # Must mention the neutral title in thinking step
    assert any("Deep researching" in t for t in thinking_titles)
    # Must show query preview in items
    assert any("AI agents 2026" in item for item in thinking_items_all)
    # FR25: thinking step title/items must NOT contain vendor name
    for t in thinking_titles:
        assert "chainlens" not in t.lower()
    for item in thinking_items_all:
        assert "chainlens" not in item.lower()


@pytest.mark.asyncio
async def test_tool_start_chainlens_long_query_is_truncated():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    steps = _thinking_step_data(chunks)
    all_items = [item for step in steps for item in step.get("items", [])]

    # Truncated at 80 chars + ellipsis (…)
    assert any("A" * 80 in item for item in all_items)
    assert any("…" in item for item in all_items)
    # 81st A not in any item
    assert not any("A" * 81 in item for item in all_items)


@pytest.mark.asyncio
async def test_tool_start_chainlens_empty_query_no_query_item():
    """Empty query → no 'Query:' item in the thinking step (graceful)."""
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-1",
            "data": {"input": {"query": ""}},
            "metadata": {},
        }
    ]
    agent = _make_agent(events)
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    # Title still present
    assert "Deep researching" in combined
    # But no "Query:" item
    assert "Query:" not in combined


# ---------------------------------------------------------------------------
# on_tool_end — success path (sources > 0)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_end_chainlens_success_shows_sources_count():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Sources found: 2" in combined
    assert "Deep researching" in combined


# ---------------------------------------------------------------------------
# on_tool_end — fallback path (no sources / empty message)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_end_chainlens_fallback_shows_research_completed():
    """AC#5 + FR25: fallback → title stays 'Deep researching', item 'Research completed'."""
    tool_output = {
        "status": "fallback",
        "provider": "nowing",
        "message": "Use generate_report...",
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    # Title stays neutral — never "fallback" as title
    assert "Deep researching" in combined
    assert "Research completed" in combined
    # FR25: thinking step title/items must not contain vendor name or expose "fallback"
    _assert_no_vendor_in_thinking(chunks)
    for step in _thinking_step_data(chunks):
        assert "fallback" not in step.get("title", "").lower()
        for item in step.get("items", []):
            assert "fallback" not in item.lower()


@pytest.mark.asyncio
async def test_tool_end_chainlens_zero_sources_shows_research_completed():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Research completed" in combined
    assert "Sources found: 0" not in combined


# ---------------------------------------------------------------------------
# on_custom_event — research_status forwarding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_event_research_status_forwarded():
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
    ss = _make_streaming_service()
    result = StreamResult()

    with patch.object(ss, "format_data", wraps=ss.format_data) as spy:
        chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        spy.assert_called_once_with("research-status", status_payload)


@pytest.mark.asyncio
async def test_custom_event_research_status_no_vendor_name_in_output():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))

    # FR25: thinking step title/items from this event must not expose vendor name
    _assert_no_vendor_in_thinking(chunks)


@pytest.mark.asyncio
async def test_custom_event_switching_phase_forwarded():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    # Phase value forwarded verbatim
    assert "switching" in combined


# ---------------------------------------------------------------------------
# Regression: non-chainlens tools are not affected (AC#8)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_chainlens_tool_not_affected():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    # generate_report titles, not Deep researching
    assert "Generating report" in combined or "Revising report" in combined
    assert "Deep researching" not in combined


@pytest.mark.asyncio
async def test_other_custom_event_not_forwarded_as_research_status():
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
    ss = _make_streaming_service()
    result = StreamResult()

    with patch.object(ss, "format_data", wraps=ss.format_data) as spy:
        await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        # Should not be called with "research-status"
        for call in spy.call_args_list:
            assert call[0][0] != "research-status"

# ---------------------------------------------------------------------------
# Defensive / boundary tests added by code review (2026-04-19)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_start_chainlens_query_exactly_80_chars_no_ellipsis():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert q in combined, "Exact-80-char query should appear unmodified"
    assert "…" not in combined, "Should NOT add ellipsis at exactly 80 chars"


@pytest.mark.asyncio
async def test_tool_start_chainlens_query_none_does_not_crash():
    """Defensive: tool_input.query=None must not raise TypeError on slicing."""
    events = [
        {
            "event": "on_tool_start",
            "name": "chainlens_deep_research",
            "run_id": "run-none",
            "data": {"input": {"query": None}},
            "metadata": {},
        }
    ]
    agent = _make_agent(events)
    ss = _make_streaming_service()
    result = StreamResult()

    # Must not raise
    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "Deep researching" in combined
    # No "Query:" item rendered (empty preview)
    assert "Query:" not in combined


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
        ss = _make_streaming_service()
        result = StreamResult()

        chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        combined = "".join(chunks)

        assert "Research completed" in combined, (
            f"Malformed output {bad_output!r} should render 'Research completed' fallback"
        )


@pytest.mark.asyncio
async def test_research_status_payload_none_does_not_crash():
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
    ss = _make_streaming_service()
    result = StreamResult()

    with patch.object(ss, "format_data", wraps=ss.format_data) as spy:
        await _collect(_stream_agent_events(agent, {}, {}, ss, result))
        # Must have been called with research-status and a dict (not None)
        called_with_dict = any(
            call[0][0] == "research-status" and isinstance(call[0][1], dict)
            for call in spy.call_args_list
        )
        assert called_with_dict, "research-status must be forwarded with a dict payload"


@pytest.mark.asyncio
async def test_research_status_strips_vendor_and_fallback_strings():
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
    ss = _make_streaming_service()
    result = StreamResult()

    chunks = await _collect(_stream_agent_events(agent, {}, {}, ss, result))
    combined = "".join(chunks)

    assert "chainlens" not in combined.lower(), "Vendor name leaked to research-status SSE"
    assert "fallback" not in combined.lower(), "Fallback hint leaked to research-status SSE"
    assert "safe_field" in combined, "Non-banned field should be preserved"
    assert "ok" in combined
