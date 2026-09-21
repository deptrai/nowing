"""Assembly test — ``build_main_agent_deepagent_middleware`` must forward
``workspace_id``/``user_id``/``client_id`` into ``build_jev_router_mw``.

Dropping those kwargs silently kills all routing telemetry (decide()
would run with ``session=None``/``user_id=None`` and ``_record_usage``
would skip every row). Heavy siblings are stubbed out so the call can
reach the builder cheaply.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.agents.chat.multi_agent_chat.main_agent.middleware.stack as stack


@pytest.mark.unit
def test_stack_forwards_telemetry_ids_to_jev_router(monkeypatch):
    # Neutralize every sibling builder the stack touches; each returns
    # None/[] and is filtered out of the final list.
    for name in (
        "build_memory_mw",
        "build_subagent_middleware_stack",
        "build_busy_mutex_mw",
        "build_otel_mw",
        "build_todos_mw",
        "build_anonymous_doc_mw",
        "build_knowledge_tree_mw",
        "build_kb_persistence_mw",
        "build_skills_mw",
        "build_mode_budget_mw",
        "build_context_editing_mw",
        "build_compaction_mw",
        "build_noop_injection_mw",
        "build_repair_mw",
        "build_permission_mw",
        "build_doom_loop_mw",
        "build_action_log_mw",
        "build_patch_tool_calls_mw",
        "build_dedup_hitl_mw",
        "build_anthropic_cache_mw",
    ):
        monkeypatch.setattr(stack, name, lambda *a, **k: None)
    monkeypatch.setattr(
        stack,
        "build_resilience_middlewares",
        lambda *a, **k: SimpleNamespace(
            model_call_limit=None,
            tool_call_limit=None,
            retry=None,
            fallback=None,
        ),
    )
    monkeypatch.setattr(stack, "build_plugin_middlewares", lambda *a, **k: [])
    monkeypatch.setattr(stack, "get_subagents_to_exclude", lambda *a, **k: [])
    monkeypatch.setattr(stack, "build_subagents", lambda *a, **k: [])
    monkeypatch.setattr(
        stack, "load_kb_write_description", lambda *a, **k: "kb desc"
    )
    monkeypatch.setattr(
        stack, "build_ask_knowledge_base_tool", lambda *a, **k: MagicMock()
    )
    monkeypatch.setattr(
        stack, "NowingCheckpointedSubAgentMiddleware", MagicMock()
    )

    spy = MagicMock(return_value=None)
    monkeypatch.setattr(stack, "build_jev_router_mw", spy)

    stack.build_main_agent_deepagent_middleware(
        llm=MagicMock(),
        tools=[],
        backend_resolver=None,
        filesystem_mode=MagicMock(),
        workspace_id=42,
        user_id="user-1",
        thread_id=7,
        visibility=MagicMock(),
        anon_session_id=None,
        available_connectors=None,
        available_document_types=None,
        mentioned_document_ids=None,
        max_input_tokens=None,
        flags=MagicMock(),
        subagent_dependencies={},
        checkpointer=MagicMock(),
        client_id="web-chat",
    )

    spy.assert_called_once()
    kwargs = spy.call_args.kwargs
    assert kwargs["workspace_id"] == 42
    assert kwargs["user_id"] == "user-1"
    assert kwargs["client_id"] == "web-chat"
