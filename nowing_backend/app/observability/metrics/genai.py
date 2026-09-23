"""GenAI / agent metric instruments."""

from __future__ import annotations

from functools import lru_cache

from app.observability.metrics.base import _add, _get_meter, _record


@lru_cache(maxsize=1)
def _model_call_duration():
    return _get_meter().create_histogram(
        "nowing.model.call.duration",
        unit="ms",
        description="Duration of Nowing LLM model calls.",
    )


@lru_cache(maxsize=1)
def _model_token_usage():
    return _get_meter().create_histogram(
        "gen_ai.client.token.usage",
        unit="{token}",
        description="Token usage reported by GenAI model responses.",
    )


@lru_cache(maxsize=1)
def _tool_call_duration():
    return _get_meter().create_histogram(
        "nowing.tool.call.duration",
        unit="ms",
        description="Duration of Nowing agent tool calls.",
    )


@lru_cache(maxsize=1)
def _tool_call_errors():
    return _get_meter().create_counter(
        "nowing.tool.call.errors",
        description="Count of Nowing agent tool call errors.",
    )


@lru_cache(maxsize=1)
def _kb_search_duration():
    return _get_meter().create_histogram(
        "nowing.kb.search.duration",
        unit="ms",
        description="Duration of Nowing knowledge-base search calls.",
    )


@lru_cache(maxsize=1)
def _compaction_runs():
    return _get_meter().create_counter(
        "nowing.compaction.runs",
        description="Count of Nowing conversation compaction runs.",
    )


@lru_cache(maxsize=1)
def _permission_asks():
    return _get_meter().create_counter(
        "nowing.permission.asks",
        description="Count of Nowing permission asks.",
    )


@lru_cache(maxsize=1)
def _interrupts():
    return _get_meter().create_counter(
        "nowing.interrupt.raised",
        description="Count of Nowing interrupts raised.",
    )


@lru_cache(maxsize=1)
def _chat_request_duration():
    return _get_meter().create_histogram(
        "nowing.chat.request.duration",
        unit="ms",
        description="Duration of Nowing streamed chat requests.",
    )


@lru_cache(maxsize=1)
def _chat_request_outcome():
    return _get_meter().create_counter(
        "nowing.chat.request.outcome",
        description="Count of Nowing chat request outcomes.",
    )


@lru_cache(maxsize=1)
def _agent_chat_public_call():
    return _get_meter().create_counter(
        "nowing.agent_chat.public_call",
        description="Count of public agent-chat API calls.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_duration():
    return _get_meter().create_histogram(
        "nowing.subagent.invoke.duration",
        unit="ms",
        description="Duration of Nowing subagent invocations.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_outcome():
    return _get_meter().create_counter(
        "nowing.subagent.invoke.outcome",
        description="Count of Nowing subagent invocation outcomes.",
    )


def record_model_call_duration(
    duration_ms: float, *, model: str | None, provider: str | None
) -> None:
    _record(
        _model_call_duration(),
        duration_ms,
        {
            "gen_ai.request.model": model,
            "gen_ai.provider.name": provider,
        },
    )


def record_model_token_usage(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    model: str | None,
    provider: str | None,
) -> None:
    base = {
        "gen_ai.request.model": model,
        "gen_ai.provider.name": provider,
        "gen_ai.operation.name": "chat",
    }
    if input_tokens is not None:
        _record(
            _model_token_usage(),
            int(input_tokens),
            {**base, "gen_ai.token.type": "input"},
        )
    if output_tokens is not None:
        _record(
            _model_token_usage(),
            int(output_tokens),
            {**base, "gen_ai.token.type": "output"},
        )


def record_tool_call_duration(duration_ms: float, *, tool_name: str) -> None:
    _record(_tool_call_duration(), duration_ms, {"tool.name": tool_name})


def record_tool_call_error(*, tool_name: str) -> None:
    _add(_tool_call_errors(), 1, {"tool.name": tool_name})


def record_kb_search_duration(
    duration_ms: float, *, workspace_id: int | None, surface: str
) -> None:
    _record(
        _kb_search_duration(),
        duration_ms,
        {"workspace.id": workspace_id, "search.surface": surface},
    )


def record_compaction_run(*, reason: str | None) -> None:
    _add(_compaction_runs(), 1, {"compaction.reason": reason or "unknown"})


def record_permission_ask(*, permission: str) -> None:
    _add(_permission_asks(), 1, {"permission.permission": permission})


def record_interrupt(*, interrupt_type: str) -> None:
    _add(_interrupts(), 1, {"interrupt.type": interrupt_type})


def record_chat_request_duration(
    duration_ms: float,
    *,
    flow: str,
    outcome: str,
    agent_mode: str | None = None,
) -> None:
    _record(
        _chat_request_duration(),
        duration_ms,
        {"chat.flow": flow, "outcome": outcome, "agent.mode": agent_mode},
    )


def record_agent_chat_public_call(
    *,
    workspace_id: int | str,
    client_id: str | None,
    agent_id: str | None,
    route: str,
    status: int,
) -> None:
    _add(
        _agent_chat_public_call(),
        1,
        {
            "workspace.id": workspace_id,
            "client.id": client_id,
            "agent.id": agent_id,
            "route": route,
            "status": status,
        },
    )


def record_chat_request_outcome(
    *,
    flow: str,
    outcome: str,
    agent_mode: str | None = None,
    error_category: str | None = None,
) -> None:
    _add(
        _chat_request_outcome(),
        1,
        {
            "chat.flow": flow,
            "outcome": outcome,
            "agent.mode": agent_mode,
            "error.category": error_category,
        },
    )


def record_subagent_invoke_duration(
    duration_ms: float,
    *,
    subagent_type: str,
    path: str | None,
    outcome: str,
) -> None:
    _record(
        _subagent_invoke_duration(),
        duration_ms,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )


def record_subagent_invoke_outcome(
    *,
    subagent_type: str,
    path: str | None,
    outcome: str,
) -> None:
    _add(
        _subagent_invoke_outcome(),
        1,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )
