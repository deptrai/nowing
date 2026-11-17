"""Regression tests spec 42.5 — approve/mixed decisions giữ pairing functionCall/functionResponse.

I/O matrix liên quan:
- APPROVE_SINGLE: approve → tool_call giữ nguyên, không duplicate ToolMessage.
- MIXED_N_CALLS: N calls, N decisions (approve + reject xen kẽ) → mỗi call
  có đúng 1 response (approve chờ tool chạy, reject có ToolMessage error).
- PARALLEL_RESUME: không đụng routing layer — chỉ assert invariant trên
  state middleware xử lý.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from pydantic import BaseModel
from typing_extensions import Annotated, TypedDict

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.permissions import (
    Rule,
    Ruleset,
    build_permission_mw,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "thread2_checkpoint.json"
)


class _Args(BaseModel):
    pass


async def _noop(**_kwargs) -> str:
    return ""


def _make_tool(name: str) -> StructuredTool:
    return StructuredTool(
        name=name,
        description=f"Tool {name}",
        coroutine=_noop,
        args_schema=_Args,
        metadata={"hitl": True},
    )


class _State(TypedDict, total=False):
    messages: Annotated[list, add_messages]


def _build_graph(pm, calls: list[dict]):
    """Graph emit N tool_calls rồi chạy qua PermissionMiddleware."""

    def emit(_state: _State) -> dict:
        return {"messages": [AIMessage(content="", tool_calls=calls)]}

    g = StateGraph(_State)
    g.add_node("emit", emit)
    g.add_node("permission", pm.aafter_model)  # type: ignore[arg-type]
    g.add_edge(START, "emit")
    g.add_edge("emit", "permission")
    g.add_edge("permission", END)
    return g.compile(checkpointer=InMemorySaver())


def _assert_pairing(messages: list, expected_call_ids: set[str]) -> None:
    """Invariant: mỗi functionResponse map đúng 1 functionCall, không duplicate.

    Trong đồ thị test, AIMessage được update qua add_messages (tool_calls bị
    shrink sau reject) nên ToolMessage reject có thể "mồ côi" so với
    AIMessage cuối — hợp lệ vì call đó TỪNG tồn tại (``expected_call_ids``).
    """
    responded: list[str] = []
    for m in messages:
        if isinstance(m, ToolMessage):
            responded.append(m.tool_call_id)
    from collections import Counter

    dupes = [k for k, v in Counter(responded).items() if v > 1]
    orphans = [r for r in responded if r not in expected_call_ids]
    assert not dupes, f"Duplicate functionResponse cho {dupes} → Gemini C1"
    assert not orphans, f"functionResponse không khớp functionCall nào: {orphans}"


def _approve_case(tool_names: list[str], decisions: list[dict], thread_id: str):
    tools = [_make_tool(n) for n in tool_names]
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[
            Ruleset(
                origin="kb",
                rules=[Rule(permission=n, pattern="*", action="ask") for n in tool_names],
            )
        ],
        tools=tools,
    )
    assert pm is not None
    calls = [
        {"name": n, "args": {}, "id": f"call_{i}", "type": "tool_call"}
        for i, n in enumerate(tool_names)
    ]
    graph = _build_graph(pm, calls)
    config = {"configurable": {"thread_id": thread_id}}
    return graph, config, calls


@pytest.mark.asyncio
async def test_approve_single_keeps_pairing():
    """APPROVE_SINGLE: approve → turn complete, không duplicate response."""
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    pending_name = raw["messages"][-1]["tool_calls"][0]["name"]
    graph, config, calls = _approve_case(
        [pending_name],
        [{"type": "approve"}],
        f"approve-single-{raw['thread_id']}",
    )
    # Seed history fixture (bỏ AIMessage pending) để mô phỏng checkpoint prod
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    result = await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config
    )
    _assert_pairing(list(result["messages"]), {calls[0]["id"]})
    # Pending call vẫn giữ trong AIMessage (approve → tool sẽ chạy)
    ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage) and m.tool_calls]
    assert ai_msgs and ai_msgs[-1].tool_calls[0]["id"] == calls[0]["id"]


@pytest.mark.asyncio
async def test_mixed_approve_and_reject_pairing():
    """MIXED_N_CALLS: 2 calls, 1 approve + 1 reject → reject có ToolMessage error, approve giữ.

    Lưu ý wire thật: PermissionMiddleware interrupt 1 lần cho TỪNG call
    (``request_permission_decision`` gọi ``interrupt`` per-call), nên resume
    payload cho call thứ 2 đi qua ``Command(resume=...)`` lần 2.
    """
    tool_names = ["gmail_send_email", "gmail_delete_draft"]
    graph, config, calls = _approve_case(tool_names, [], "mixed-approve-reject")
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    # Resume 1: approve call_0
    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config
    )
    # Resume 2: reject call_1 kèm feedback
    result = await graph.ainvoke(
        Command(resume={"decisions": [{"type": "reject", "message": "Đừng xoá"}]}),
        config,
    )
    msgs = list(result["messages"])
    _assert_pairing(msgs, {c["id"] for c in calls})
    # Reject call bị drop khỏi AIMessage + có ToolMessage error cancelled
    ai_msgs = [m for m in msgs if isinstance(m, AIMessage) and m.tool_calls]
    kept_ids = [tc["id"] for tc in ai_msgs[-1].tool_calls]
    assert calls[0]["id"] in kept_ids, "approved call phải được giữ"
    assert calls[1]["id"] not in kept_ids, "rejected call phải bị drop"
    reject_msgs = [
        m
        for m in msgs
        if isinstance(m, ToolMessage) and m.tool_call_id == calls[1]["id"]
    ]
    assert len(reject_msgs) == 1, "reject phải có ĐÚNG 1 ToolMessage"
    assert reject_msgs[0].status == "error"
    assert reject_msgs[0].additional_kwargs["error"]["code"] == "cancelled"
    assert "Đừng xoá" in str(reject_msgs[0].content), "feedback phải nằm trong content"


@pytest.mark.asyncio
async def test_all_reject_emits_one_response_per_call():
    """N calls, N rejects → mỗi call có đúng 1 ToolMessage error (count match)."""
    tool_names = ["gmail_send_email", "gmail_delete_draft", "calendar_create_event"]
    graph, config, calls = _approve_case(tool_names, [], "all-reject")
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    result = None
    for i in range(len(tool_names)):
        result = await graph.ainvoke(
            Command(
                resume={"decisions": [{"type": "reject", "message": f"Không làm bước {i}"}]}
            ),
            config,
        )
    msgs = list(result["messages"])
    _assert_pairing(msgs, {c["id"] for c in calls})
    for call in calls:
        responses = [
            m
            for m in msgs
            if isinstance(m, ToolMessage) and m.tool_call_id == call["id"]
        ]
        assert len(responses) == 1, (
            f"{call['id']}: expected 1 functionResponse, got {len(responses)} — "
            "Gemini C1 mismatch"
        )
