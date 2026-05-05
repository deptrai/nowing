"""End-to-end resume-bridge tests against a real LangGraph subagent.

Builds a minimal Pregel subagent that calls ``interrupt(...)`` and drives the
``task`` tool directly with a hand-crafted ``ToolRuntime``. Exercises the only
runtime contract we own: parent stashes a decision in
``config["configurable"]["surfsense_resume_value"]`` -> bridge forwards it as
``Command(resume={interrupt_id: value})`` -> subagent completes -> return value
reflects the decision.

We pause the subagent **outside** the parent task tool (calling
``subagent.ainvoke`` directly) to skip the ``_lg_interrupt`` re-raise path,
which requires a parent runnable context. The bridge logic under test is the
*resume* dispatch, not the propagation; propagation is exercised separately in
its own module's tests.
"""

from __future__ import annotations

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.main_agent.graph.middleware.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)


class _SubagentState(TypedDict, total=False):
    messages: list
    decision_text: str


def _build_single_interrupt_subagent():
    """Subagent that interrupts once, then echoes the resume decision into state."""

    def approve_node(state):
        from langchain_core.messages import AIMessage

        decision = interrupt(
            {
                "action_requests": [
                    {
                        "name": "do_thing",
                        "args": {"x": 1},
                        "description": "test action",
                    }
                ],
                "review_configs": [{}],
            }
        )
        # Capture the resume payload verbatim so the test can assert the
        # bridge forwarded it intact (no reshape, no scalar broadcast).
        return {
            "messages": [AIMessage(content="done")],
            "decision_text": repr(decision),
        }

    graph = StateGraph(_SubagentState)
    graph.add_node("approve", approve_node)
    graph.add_edge(START, "approve")
    graph.add_edge("approve", END)
    return graph.compile(checkpointer=InMemorySaver())


def _make_runtime(config: dict) -> ToolRuntime:
    return ToolRuntime(
        state={"messages": [HumanMessage(content="seed")]},
        context=None,
        config=config,
        stream_writer=None,
        tool_call_id="parent-tcid-1",
        store=None,
    )


@pytest.mark.asyncio
async def test_resume_bridge_dispatches_decision_into_pending_subagent():
    """Side-channel decision -> targeted Command(resume) -> subagent completes."""
    subagent = _build_single_interrupt_subagent()
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "approver",
                "description": "approves things",
                "runnable": subagent,
            }
        ]
    )

    # 1. Pause the subagent directly so we can test only the resume path.
    parent_config: dict = {
        "configurable": {"thread_id": "shared-thread"},
        "recursion_limit": 100,
    }
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)
    snap = await subagent.aget_state(parent_config)
    assert snap.tasks and snap.tasks[0].interrupts, (
        "fixture broken: subagent should be paused on its interrupt"
    )

    # 2. Stash the user's decision on the side-channel — this is what
    #    ``stream_resume_chat`` does in production.
    parent_config["configurable"]["surfsense_resume_value"] = {
        "decisions": ["APPROVED"]
    }
    runtime = _make_runtime(parent_config)

    # 3. Drive the bridge. Subagent has no remaining interrupt after resume,
    #    so propagation will not call ``_lg_interrupt`` (no parent ctx needed).
    result = await task_tool.coroutine(
        description="please approve",
        subagent_type="approver",
        runtime=runtime,
    )

    assert isinstance(result, Command)
    update = result.update
    # Bridge forwards the side-channel payload **verbatim** to the
    # subagent's ``interrupt()``. A scalar broadcast or accidental
    # unwrap would change this shape and we want to catch that.
    assert update["decision_text"] == repr({"decisions": ["APPROVED"]})

    # 4. Side-channel was consumed; a stale replay would re-prompt the user.
    assert "surfsense_resume_value" not in parent_config["configurable"]

    # 5. Subagent moved past the interrupt (no pending tasks remain).
    final = await subagent.aget_state(parent_config)
    assert not final.tasks or all(not t.interrupts for t in final.tasks)


@pytest.mark.asyncio
async def test_pending_interrupt_without_resume_value_raises_runtime_error():
    """Bridge must fail loud if a paused subagent has no decision queued.

    The fail-open alternative (silently re-invoking) would re-fire the
    same interrupt to the user. The error surfaces a real broken bridge
    instead of confusing duplicate approval cards.
    """
    subagent = _build_single_interrupt_subagent()
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "approver",
                "description": "approves things",
                "runnable": subagent,
            }
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "guard-thread"},
        "recursion_limit": 100,
    }
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)
    snap = await subagent.aget_state(parent_config)
    assert snap.tasks and snap.tasks[0].interrupts, "fixture broken"

    # No surfsense_resume_value injected — bridge must refuse to proceed.
    runtime = _make_runtime(parent_config)

    with pytest.raises(RuntimeError, match="resume bridge is broken"):
        await task_tool.coroutine(
            description="please approve",
            subagent_type="approver",
            runtime=runtime,
        )
