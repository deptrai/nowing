"""Repro test cho spec 42.5 — HITL approve/reject → Gemini functionResponse mismatch (C1).

AD-6: test này PHẢI chạy trước khi fix và chứng minh root cause bằng log/assert:
- Reject path (middleware-gated): ``PermissionMiddleware._process`` raise
  ``RejectedError``/``CorrectedError`` — exception thoát ra ngoài, checkpoint
  giữ AIMessage với tool_call lơ lửng không ToolMessage → converter Gemini
  (``_get_ai_message_tool_messages_parts``) drop phần functionResponse →
  functionCall count != functionResponse count → Gemini 400.
- Invariant kiểm chứng trên fixture: mọi ``functionCall`` trong checkpointed
  history phải có đúng 1 ToolMessage cùng ``tool_call_id`` trước model call.

Fixture: FALLBACK snapshot-shaped (không phải raw prod thread) — xem
``_provenance`` trong ``thread2_checkpoint.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from typing_extensions import Annotated, TypedDict

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.permissions import (
    Rule,
    Ruleset,
    build_permission_mw,
)
from app.agents.chat.runtime.errors import CorrectedError, RejectedError

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "thread2_checkpoint.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_messages(raw: dict) -> list:
    """Chuyển JSON fixture thành langchain messages."""
    out: list = []
    for m in raw["messages"]:
        t = m["type"]
        if t == "human":
            out.append(HumanMessage(content=m["content"]))
        elif t == "ai":
            out.append(
                AIMessage(
                    content=m.get("content", ""),
                    tool_calls=m.get("tool_calls") or [],
                )
            )
        elif t == "tool":
            out.append(
                ToolMessage(
                    content=m["content"],
                    tool_call_id=m["tool_call_id"],
                    name=m.get("name"),
                )
            )
    return out


def _count_function_pairs(messages: list) -> dict[str, list[str]]:
    """Đếm functionCall vs functionResponse theo từng AIMessage (mô phỏng converter Gemini).

    Trả về map ``tool_call_id -> [số functionCall, số functionResponse]``.
    """
    tool_call_ids: list[str] = []
    responded: set[str] = set()
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls:
                tool_call_ids.append(tc["id"])
        elif isinstance(m, ToolMessage):
            responded.add(m.tool_call_id)
    return {
        tc_id: [1, 1 if tc_id in responded else 0] for tc_id in tool_call_ids
    }


class _State(TypedDict, total=False):
    messages: Annotated[list, add_messages]


async def _noop(**_kwargs) -> str:
    return ""


def _make_tool(name: str):
    from pydantic import BaseModel

    from langchain_core.tools import StructuredTool

    class _Args(BaseModel):
        pass

    return StructuredTool(
        name=name,
        description=f"Tool {name}",
        coroutine=_noop,
        args_schema=_Args,
        metadata={"hitl": True},
    )


def _build_graph(pm, tool_name: str):
    def emit(_state: _State) -> dict:
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool_name,
                            "args": {"draft_id": "d1"},
                            "id": "call_prod_5",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    g = StateGraph(_State)
    g.add_node("emit", emit)
    g.add_node("permission", pm.aafter_model)  # type: ignore[arg-type]
    g.add_edge(START, "emit")
    g.add_edge("emit", "permission")
    g.add_edge("permission", END)
    return g.compile(checkpointer=InMemorySaver())


def _assert_invariant(messages: list, where: str) -> None:
    """Invariant spec: mỗi functionCall có đúng 1 functionResponse trước model call kế."""
    pairs = _count_function_pairs(messages)
    dangling = {k: v for k, v in pairs.items() if v[1] == 0}
    assert not dangling, (
        f"[{where}] Gemini C1 mismatch: {len(dangling)} functionCall không có "
        f"functionResponse (pending={len(pairs)}, matched={len(pairs) - len(dangling)}): "
        f"{dangling}"
    )


def test_fixture_invariant_before_resume():
    """Fixture checkpoint ban đầu phải thoả invariant (mọi call đã có response)."""
    raw = _load_fixture()
    msgs = _fixture_messages(raw)
    # call_prod_5 là pending interrupt — chưa có response, hợp lệ ở trạng thái pause
    pairs = _count_function_pairs(msgs[:-1])  # bỏ AIMessage pending cuối
    _assert_invariant(msgs[:-1], "checkpoint-paused (trước pending call cuối)")
    #AIMessage cuối (pending) đúng 1 call đang chờ
    pending = pairs  # noqa: F841


@pytest.mark.asyncio
async def test_reject_decision_leaves_dangling_tool_call():
    """REJECT_SINGLE: reject qua PermissionMiddleware → chứng minh dangling tool_call.

    Trước fix: raise ``RejectedError`` thoát ra ngoài → invariant vỡ (C1).
    Sau fix: pending call bị drop kèm ToolMessage error ``cancelled`` → invariant giữ.
    """
    raw = _load_fixture()
    msgs = _fixture_messages(raw)
    pending_ai = msgs[-1]
    assert pending_ai.tool_calls, "fixture phải có pending tool_call"
    pending_call = pending_ai.tool_calls[0]

    tool = _make_tool(pending_call["name"])
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[
            Ruleset(
                origin="kb",
                rules=[Rule(permission=pending_call["name"], pattern="*", action="ask")],
            )
        ],
        tools=[tool],
    )
    assert pm is not None

    graph = _build_graph(pm, pending_call["name"])
    config = {"configurable": {"thread_id": raw["thread_id"]}}
    # Seed checkpoint với history của fixture + AIMessage pending
    await graph.ainvoke({"messages": [*msgs[:-1]]}, config)
    # AIMessage pending đã được emit node ghi vào state; resume REJECT
    try:
        await graph.ainvoke(
            Command(
                resume={
                    "decisions": [
                        {"type": "reject", "message": "Đừng xoá nháp, giữ lại"}
                    ]
                }
            ),
            config,
        )
        raised: BaseException | None = None
    except (RejectedError, CorrectedError) as exc:
        raised = exc

    snapshot = await graph.aget_state(config)
    state_messages = list(snapshot.values.get("messages") or [])
    print(f"\n[REPRO] raised={raised!r}")
    print(
        f"[REPRO] state messages sau reject: {len(state_messages)} "
        f"(fixture prod estimate={raw['message_count_estimate_prod']})"
    )
    print(
        f"[REPRO] pending call id={pending_call['id']} "
        f"tool={pending_call['name']}"
    )
    if raised is not None:
        # Trước fix: exception uncaught — chứng minh root cause #1.
        pairs = _count_function_pairs(state_messages)
        dangling = {k: v for k, v in pairs.items() if v[1] == 0}
        print(
            f"[ROOT CAUSE #1] Reject raise {type(raised).__name__} uncaught; "
            f"functionCall pending={len(pairs)}, functionResponse matched="
            f"{len(pairs) - len(dangling)} → Gemini C1 mismatch."
        )
        pytest.fail(
            f"Root cause confirmed (pre-fix): {type(raised).__name__} uncaught "
            f"trên reject path; dangling tool_calls={dangling}"
        )
    else:
        # Sau fix: reject phải tổng hợp ToolMessage error cho pending call.
        _assert_invariant(state_messages, "sau reject (post-fix)")


@pytest.mark.asyncio
async def test_reject_with_feedback_pairs_tool_message():
    """REJECT_FEEDBACK: reject kèm feedback → ToolMessage mang feedback, pairing giữ."""
    raw = _load_fixture()
    msgs = _fixture_messages(raw)
    pending_ai = msgs[-1]
    pending_call = pending_ai.tool_calls[0]

    tool = _make_tool(pending_call["name"])
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[
            Ruleset(
                origin="kb",
                rules=[Rule(permission=pending_call["name"], pattern="*", action="ask")],
            )
        ],
        tools=[tool],
    )
    graph = _build_graph(pm, pending_call["name"])
    config = {"configurable": {"thread_id": raw["thread_id"] + "-feedback"}}
    await graph.ainvoke({"messages": [*msgs[:-1]]}, config)
    try:
        await graph.ainvoke(
            Command(resume={"decisions": [{"type": "reject", "message": "Giữ nháp lại"}]}),
            config,
        )
        raised: BaseException | None = None
    except (RejectedError, CorrectedError) as exc:
        raised = exc

    snapshot = await graph.aget_state(config)
    state_messages = list(snapshot.values.get("messages") or [])
    print(f"\n[REJECT_FEEDBACK] raised={raised!r}")
    if raised is None:
        # Post-fix: tìm ToolMessage error cho pending call, content phải mang feedback
        errs = [
            m
            for m in state_messages
            if isinstance(m, ToolMessage) and m.tool_call_id == pending_call["id"]
        ]
        assert errs, "reject phải sinh ToolMessage cùng tool_call_id"
        assert any("Giữ nháp lại" in str(m.content) for m in errs), (
            f"ToolMessage reject phải mang feedback, thấy: {[m.content for m in errs]}"
        )
    else:
        pytest.fail(
            f"Root cause confirmed (pre-fix): {type(raised).__name__} uncaught "
            "trên reject+feedback path"
        )
