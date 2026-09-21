"""Tests for ToolCallNameRepairMiddleware."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.agents.chat.multi_agent_chat.main_agent.middleware.tool_call_repair.middleware import (
    ToolCallNameRepairMiddleware,
)
from app.agents.chat.multi_agent_chat.main_agent.tools.invalid_tool import (
    INVALID_TOOL_NAME,
)

pytestmark = pytest.mark.unit


def _make_state(message: AIMessage) -> dict:
    return {"messages": [message]}


class _FakeRuntime:
    def __init__(self, context: object | None = None) -> None:
        self.context = context


class TestRepair:
    def test_passthrough_when_name_matches(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "echo", "args": {}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is None  # no change

    def test_lowercase_repair(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "Echo", "args": {"x": 1}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        repaired = out["messages"][0]
        assert repaired.tool_calls[0]["name"] == "echo"

    def test_invalid_fallback_when_no_match(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo", INVALID_TOOL_NAME},
            fuzzy_match_threshold=None,
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "totally_different_name", "args": {"k": "v"}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        repaired_call = out["messages"][0].tool_calls[0]
        assert repaired_call["name"] == INVALID_TOOL_NAME
        assert repaired_call["args"]["tool"] == "totally_different_name"
        assert "totally_different_name" in repaired_call["args"]["error"]

    def test_no_invalid_means_skip_when_unknown(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "unknown", "args": {}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        # No repair available; original returned unchanged (no update)
        assert out is None

    def test_fuzzy_match_works_when_enabled(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"search_documents"},
            fuzzy_match_threshold=0.7,
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "search_docments", "args": {}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        assert out["messages"][0].tool_calls[0]["name"] == "search_documents"

    def test_skips_when_no_messages(self) -> None:
        mw = ToolCallNameRepairMiddleware(registered_tool_names={"echo"})
        out = mw.after_model({"messages": []}, _FakeRuntime())
        assert out is None

    def test_runtime_context_extends_registered(self) -> None:
        from types import SimpleNamespace

        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "DynamicTool", "args": {}, "id": "1"},
            ],
        )
        runtime = _FakeRuntime(SimpleNamespace(registered_tool_names=["dynamictool"]))
        out = mw.after_model(_make_state(msg), runtime)
        assert out is not None
        assert out["messages"][0].tool_calls[0]["name"] == "dynamictool"


_MARKUP = (
    '<|open|>tools<|sep|><|open|>call tool="task" index="1"<|sep|>'
    '<|open|>argument key="subagent_type" type="string"<|sep|>chainlens'
    '<|close|>argument<|sep|>'
    '<|open|>argument key="description" type="string"<|sep|>Find a code example'
    '<|close|>argument<|sep|><|close|>call<|sep|><|close|>tools<|sep|>'
    "<|close|>message<|sep|>"
)


class TestMarkupRecovery:
    """Stage 0 — tool calls emitted as text markup instead of tool_calls."""

    def test_markup_only_message_recovers_tool_call(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"task"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(content=_MARKUP)
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        repaired = out["messages"][0]
        assert repaired.tool_calls == [
            {
                "name": "task",
                "args": {
                    "subagent_type": "chainlens",
                    "description": "Find a code example",
                },
                "id": "call_markup_0",
                "type": "tool_call",
            }
        ]
        # Markup stripped from the visible content.
        assert repaired.content == ""
        # Stage-1/2 metadata absent — the name was already valid.
        assert "repair" not in (repaired.response_metadata or {})

    def test_markup_deduped_against_structured_call(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"task"}, fuzzy_match_threshold=None
        )
        structured = {
            "name": "task",
            "args": {
                "subagent_type": "chainlens",
                "description": "Find a code example",
            },
            "id": "call_x",
            "type": "tool_call",
        }
        msg = AIMessage(content=_MARKUP, tool_calls=[structured])
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        # The recovered markup call matches the structured one — not duplicated.
        assert out["messages"][0].tool_calls == [structured]
        assert out["messages"][0].content == ""

    def test_markup_unknown_name_routes_to_invalid(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"task", INVALID_TOOL_NAME},
            fuzzy_match_threshold=None,
        )
        bad_markup = _MARKUP.replace('tool="task"', 'tool="Bogus"').replace(
            "chainlens", "x"
        )
        msg = AIMessage(content=bad_markup)
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        repaired = out["messages"][0]
        assert repaired.tool_calls[0]["name"] == INVALID_TOOL_NAME
        assert repaired.tool_calls[0]["args"]["tool"] == "Bogus"
        assert repaired.content == ""

    def test_plain_text_without_markup_untouched(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"task"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(content="Just a normal answer.")
        assert mw.after_model(_make_state(msg), _FakeRuntime()) is None

    def test_markup_inside_list_content_stripped_per_block(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"task"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content=[
                {"type": "text", "text": "Before. " + _MARKUP + " After"},
            ]
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        repaired = out["messages"][0]
        assert repaired.tool_calls[0]["name"] == "task"
        # Surrounding text preserved, markup gone.
        assert repaired.content == [{"type": "text", "text": "Before.  After"}]

    def test_partial_markup_without_call_body_ignored(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"task"}, fuzzy_match_threshold=None
        )
        # A truncated emission: stray tokens but no complete call block.
        msg = AIMessage(content="<|open|>tools<|sep|><|close|>tools<|sep|>")
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        # No calls recovered → nothing to do → no update.
        assert out is None
